"""Video mode: where the person is inside each slice of the cut — the focus of the camera move.

A push-in over a screen recording crops text away, so the default move only happens where a face
is actually found. Without the model, or without a face, the segment is left alone: `rostos()`
simply has no entry for it, and corte.py gives that segment no camera.

The samples are cached in .estudio/enquadre.json, keyed by source and frame range, so re-running
`montar` after an edit costs nothing for the slices that did not move.
"""
from __future__ import annotations

import json

import cv2

from ambiente import Ambiente
from projeto import Projeto

CONFIANCA = 0.6
AMOSTRAS = 3
AREA_MINIMA = 0.006  # below this the face is a dot in a wide shot, not someone talking to camera


def _detector(amb: Ambiente, w: int, h: int):
    if not amb.modelo_rosto.exists():
        return None
    try:
        return cv2.FaceDetectorYN.create(str(amb.modelo_rosto), "", (w, h), CONFIANCA, 0.3, 5000)
    except (cv2.error, AttributeError):
        return None


def _mediana(vs: list[float]) -> float:
    vs = sorted(vs)
    return vs[len(vs) // 2]


def _amostrar(cap, det, f0: int, f1: int, w: int, h: int) -> list[float] | None:
    """Median face centre over a few frames of the slice, in 0..1 — None when nobody is there."""
    xs, ys, areas = [], [], []
    for k in range(AMOSTRAS):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f0 + (f1 - f0) * (k + 0.5) / max(1, AMOSTRAS)))
        ok, im = cap.read()
        if not ok:
            continue
        try:
            _, achados = det.detect(im)
        except cv2.error:
            continue
        if achados is None or not len(achados):
            continue
        x, y, fw, fh = max(achados, key=lambda r: r[2] * r[3])[:4]
        xs.append(float((x + fw / 2) / w))
        ys.append(float((y + fh / 2) / h))
        areas.append(float(fw * fh) / (w * h))
    # a face in fewer than half the samples means the shot is not really about the person
    if len(xs) * 2 < AMOSTRAS or _mediana(areas) < AREA_MINIMA:
        return None
    return [round(min(1.0, max(0.0, _mediana(xs))), 4), round(min(1.0, max(0.0, _mediana(ys))), 4)]


def rostos(p: Projeto, amb: Ambiente | None, trechos: list[dict]) -> dict:
    """{segment id: [x, y] in 0..1} for the slices where somebody is on screen.

    `trechos` items: {"id", "source", "f0", "f1"} with f0/f1 in frames of that source."""
    # never cache a "no face" that only means the model was missing: with the model installed
    # later, a stale null would keep the camera parked forever
    if amb is None or not amb.modelo_rosto.exists():
        return {}
    cache_p = p.build / "enquadre.json"
    try:
        cache = json.loads(cache_p.read_text()) if cache_p.exists() else {}
    except json.JSONDecodeError:
        cache = {}
    fora, mudou, caps, dets = {}, False, {}, {}
    try:
        for t in trechos:
            chave = f"{t['source']}:{t['f0']}:{t['f1']}"
            if chave not in cache:
                nome = t["source"]
                if nome not in caps:
                    cap = cv2.VideoCapture(str(p.fonte(nome)))
                    if not cap.isOpened():
                        cap.release()
                        caps[nome], dets[nome] = None, None
                    else:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1
                        caps[nome], dets[nome] = cap, (_detector(amb, w, h), w, h)
                cap = caps.get(nome)
                det = dets.get(nome)
                if cap is None or det is None or det[0] is None:
                    continue  # unreadable source or detector failed: leave the cache alone
                cache[chave] = _amostrar(cap, det[0], t["f0"], t["f1"], det[1], det[2])
                mudou = True
            if cache.get(chave):
                fora[t["id"]] = cache[chave]
    finally:
        for cap in caps.values():
            if cap is not None:
                cap.release()
    if mudou:
        p.build.mkdir(parents=True, exist_ok=True)
        cache_p.write_text(json.dumps(cache, indent=1))
    return fora
