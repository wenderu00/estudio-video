"""Lays out narration lines, pauses, scene pre/post-rolls and transition overlaps, and resolves
the script's time anchors into frames.

Outputs per format: .estudio/timeline-<fmt>.json (the Remotion input props), line audio with
lengthened "..." pauses (.estudio/work/lines_<fmt>/), saida/<slug>[-shorts].srt and, for the
main format, saida/roteiro.md.
"""
from __future__ import annotations

import json

import numpy as np
from scipy.io import wavfile

from narracao import line_key
from projeto import (FORMATOS, AnchorError, Projeto, find_line, norm, parse_anchor, split_base)

SR = 48000
# transitions where the incoming scene is drawn over the outgoing one
OVERLAP = {"splatter", "fog", "drip", "slash", "whip", "zoomBlur", "crossfade"}
ELLIPSIS_EXTRA = {"main": 0.38, "shorts": 0.12}
SKIP_RESOLVE = {"lines", "transitionIn", "transitionOut"}


def ellipsis_word_indices(text: str, words: list) -> list[int]:
    """Indices of words that are immediately followed by an internal '...'."""
    targets = [norm(t) for t in text.split()[:-1] if t.endswith("...")]
    out, j = [], 0
    for tgt in targets:
        while j < len(words) and norm(words[j]["w"]) != tgt:
            j += 1
        if j < len(words) - 1:
            out.append(j)
        j += 1
    return out


def process_line(p: Projeto, meta: dict, extra: float, out_wav):
    _, x = wavfile.read(p.tts / f"{meta['key']}.wav")
    words = [dict(w) for w in meta["words"]]
    idxs = ellipsis_word_indices(meta["text"], words) if extra > 0 else []
    pieces, last = [], 0
    for i in idxs:
        cut = int(((words[i]["t"] + words[i]["d"] + words[i + 1]["t"]) / 2) * SR)
        pieces += [x[last:cut], np.zeros(int(extra * SR), np.float32)]
        last = cut
        for w in words[i + 1:]:
            w["t"] = round(w["t"] + extra, 4)
    pieces.append(x[last:])
    y = np.concatenate(pieces).astype(np.float32)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(out_wav, SR, y)
    return len(y) / SR, words


def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str, width=42) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    lines.append(cur)
    if len(lines) > 2:  # rebalance into 2 lines
        half = len(words) // 2
        lines = [" ".join(words[:half]), " ".join(words[half:])]
    return "\n".join(lines)


# -------------------------------------------------------------------- anchors
def resolve_at(spec, scene: dict, fps: int) -> int:
    base, off, unit = parse_anchor(spec)
    off_f = round(off if unit == "f" else off * fps)
    if base is None:
        f = 0
    elif base == "start":
        f = 0
    elif base == "end":
        f = scene["durFrames"]
    else:
        ref, edge, word = split_base(base)
        ln = find_line(scene["lines"], ref)
        if ln is None:
            raise AnchorError(f"cena `{scene['id']}`: âncora `{spec}` — fala `{ref}` não existe")
        if word:
            w = next((w for w in ln["words"] if norm(w["w"]) == norm(word)), None)
            if w is None:
                w = next((w for w in ln["words"] if norm(w["w"]).startswith(norm(word)[:4])), None)
            if w is None:
                raise AnchorError(f"cena `{scene['id']}`: âncora `{spec}` — palavra `{word}` não encontrada na narração")
            f = w["rel"]
        elif edge == "end":
            f = ln["rel"] + ln["durFrames"]
        else:
            f = ln["rel"]
    return max(0, min(scene["durFrames"], f + off_f))


def resolve_scene(obj, scene: dict, fps: int):
    """Adds f (scene-relative frame) next to every `at` key; sorts camera keyframe lists."""
    if isinstance(obj, dict):
        if "at" in obj:
            obj["f"] = resolve_at(obj["at"], scene, fps)
        for k, v in obj.items():
            if k not in SKIP_RESOLVE:
                resolve_scene(v, scene, fps)
    elif isinstance(obj, list):
        for v in obj:
            resolve_scene(v, scene, fps)
        if obj and all(isinstance(v, dict) and "f" in v and "s" in v for v in obj):
            obj.sort(key=lambda v: v["f"])


# -------------------------------------------------------------------- build
def build(p: Projeto, fmt: str) -> dict:
    data = p.roteiro(fmt)
    fps = data["fps"]
    F = lambda s: int(round(s * fps))  # noqa: E731
    extra_default = ELLIPSIS_EXTRA[fmt]
    voices = data["voices"]
    art_meta = json.loads((p.art / "art.json").read_text()) if (p.art / "art.json").exists() else {}
    scenes_out, sfx, srt_cues = [], [], []
    prev_end = 0.0
    for si, sc in enumerate(data["scenes"]):
        tin = sc.get("transitionIn", {"type": "none", "dur": 0})
        overlap = tin.get("dur", 0) if tin["type"] in OVERLAP else 0.0
        start = max(0.0, prev_end - overlap) if si > 0 else 0.0
        t = start + sc.get("preRoll", 1.0)
        lines_out = []
        for ln in sc["lines"]:
            v = voices[ln["speaker"]]
            meta = json.loads((p.tts / f"{line_key(v, ln['text'])}.json").read_text())
            dur, words = process_line(p, meta, ln.get("ellipsisPause", extra_default), p.work / f"lines_{fmt}" / f"{ln['id']}.wav")
            l0 = t
            out_ln = {
                "id": ln["id"], "speaker": ln["speaker"], "text": ln["text"],
                "screen": ln.get("screen", ""), "screenText": ln.get("screenText", ln["text"]),
                "t": round(l0, 4), "dur": round(dur, 4), "from": F(l0), "durFrames": max(1, F(dur)),
                "words": [{"w": w["w"], "t": round(l0 + w["t"], 4), "f": F(l0 + w["t"]), "d": max(1, F(w["d"]))} for w in words],
                "italic": ln.get("italic", bool(v.get("italic"))),
            }
            for k in ("hl", "hlFrom"):
                if k in ln:
                    out_ln[k] = ln[k]
            lines_out.append(out_ln)
            for s in ln.get("sfx", []):
                at = s.get("at", "start")
                if at == "end":
                    base = l0 + dur
                elif at.startswith("word:"):
                    tgt = norm(at[5:])
                    base = next((l0 + w["t"] for w in words if norm(w["w"]) == tgt), l0)
                else:
                    base = l0
                sfx.append({"name": s["name"], "t": round(base + s.get("offset", 0.0), 4), "scene": sc["id"],
                            "vel": s.get("vel", 1.0)})
            srt_cues.append((l0, l0 + dur, ln["text"]))
            t = l0 + dur + ln.get("pause", 0.0)
        end = t + sc.get("postRoll", 1.0)
        tout = sc.get("transitionOut")
        out = {k: v for k, v in sc.items() if k not in ("lines", "preRoll", "postRoll")}
        out.update({
            "t0": round(start, 4), "t1": round(end, 4), "from": F(start), "durFrames": F(end) - F(start),
            "transitionIn": {"type": tin["type"], "frames": F(tin.get("dur", 0))},
            "transitionOut": ({"type": tout["type"], "frames": F(tout.get("dur", 0)), "holdFrames": F(tout.get("hold", 0))} if tout else None),
            "lines": lines_out,
        })
        out.setdefault("accent", "red")
        for lo in out["lines"]:  # rel frames for convenience inside <Sequence>
            lo["rel"] = lo["from"] - out["from"]
            for w in lo["words"]:
                w["rel"] = w["f"] - out["from"]
        resolve_scene(out, out, fps)
        scenes_out.append(out)
        prev_end = end
    total = scenes_out[-1]["t1"]
    duration_frames = scenes_out[-1]["from"] + scenes_out[-1]["durFrames"]
    tl = {
        "format": fmt, "title": data["title"], "fps": fps, "width": data["width"], "height": data["height"],
        "durationInFrames": duration_frames, "duration": round(total, 4),
        "audio": f"audio/mix-{fmt}.wav", "images": len(p.imagens()),
        "palette": p.cfg["palette"], "art": art_meta,
        "scenes": scenes_out, "sfx": sorted(sfx, key=lambda s: s["t"]),
    }
    out_json = p.timeline_path(fmt)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(tl, ensure_ascii=False, indent=1))

    # SRT: one cue per line, lingering up to 0.6 s but never past the next cue
    srt = []
    for i, (a, b, txt) in enumerate(srt_cues):
        nxt = srt_cues[i + 1][0] if i + 1 < len(srt_cues) else b + 2
        b2 = min(b + 0.6, nxt - 0.05)
        srt.append(f"{i + 1}\n{fmt_srt(a)} --> {fmt_srt(b2)}\n{wrap(txt.replace('...', '…'))}\n")
    p.saida.mkdir(parents=True, exist_ok=True)
    p.srt(fmt).write_text("\n".join(srt), encoding="utf-8")

    print(f"[{fmt}] total {total:.2f}s = {duration_frames} quadros")
    for s in scenes_out:
        print(f"  {s['id']:10s} {s['t0']:7.2f} → {s['t1']:7.2f}  ({s['t1'] - s['t0']:5.2f}s)  entrada={s['transitionIn']['type']}")
    if fmt == "shorts" and total > 60:
        print(f"  ⚠ Shorts com {total:.1f}s: o YouTube só trata como Shorts vídeos de até 60 s (encurte falas/pausas)")
    return tl


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def scene_name(sc: dict) -> str:
    if sc.get("name"):
        return sc["name"]
    if sc.get("titleLines"):
        t = " ".join("".join(seg["t"] for seg in line).strip() for line in sc["titleLines"])
        return f"{sc.get('number', '')} · {t.capitalize()}".strip(" ·")
    return {"opening": "Abertura", "moral": "Moral", "outro": "Encerramento"}.get(sc["kind"], sc["id"])


def write_roteiro_md(p: Projeto, tl: dict):
    voices = p.roteiro(tl["format"])["voices"]
    label = lambda k: voices.get(k, {}).get("label") or k.capitalize()  # noqa: E731
    vozes = " · ".join(f"**{label(k)}** ({v['voice'].split('-')[2].replace('Neural', '')})" for k, v in voices.items())
    md = [f"# Roteiro — {tl['title']}", "",
          f"Duração: **{mmss(tl['duration'])}** · {tl['width']}×{tl['height']} · {tl['fps']} fps", "",
          f"Vozes: {vozes}", ""]
    sfx_by_scene = {}
    for s in tl["sfx"]:
        sfx_by_scene.setdefault(s["scene"], []).append(s)
    for sc in tl["scenes"]:
        md += [f"## {mmss(sc['t0'])} — {scene_name(sc)} (imagem {sc['image']})", "",
               "| Tempo | Voz | Fala | Em tela |", "|---|---|---|---|"]
        for ln in sc["lines"]:
            md.append(f"| {mmss(ln['t'])} | {label(ln['speaker'])} | {ln['text']} | {ln['screenText']} |")
        fx = ", ".join(f"{s['name']} ({mmss(s['t'])})" for s in sfx_by_scene.get(sc["id"], []))
        md += ["", f"Transição de entrada: `{sc['transitionIn']['type']}` · Trilha: `{sc.get('music', '')}`" + (f" · SFX: {fx}" if fx else ""), ""]
    (p.saida / "roteiro.md").write_text("\n".join(md), encoding="utf-8")


def gerar(p: Projeto) -> dict:
    out = {}
    for fmt in p.formatos():
        out[fmt] = build(p, fmt)
    first = "main" if "main" in out else next(iter(out), None)
    if first:
        write_roteiro_md(p, out[first])
    return out
