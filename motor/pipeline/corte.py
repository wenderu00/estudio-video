"""Video mode: the cut list (corte.json) becomes a timeline, an edited voice track and the captions.

Every in/out is quantised to the output frame grid before anything else — the ffmpeg cut and the
numpy audio slice then use exactly the same boundaries, which is what keeps picture and sound in
sync and makes `qa` able to demand `quadros == timeline`.

Outputs: .estudio/timeline-main.json (also what the montage reads), .estudio/work/voz-main.wav,
saida/<slug>.srt and .estudio/work/legendas.ass.
"""
from __future__ import annotations

import json

import numpy as np
from scipy.io import wavfile

import fonte
from projeto import (FORMATOS, TRANSICOES_CORTE, AnchorError, Projeto, parse_tempo, resolver_look)
from timeline import fmt_srt, wrap

SR = 48000
FMT = "main"
EMENDA = 0.008  # short fade on every audio edge, to avoid clicks
FALANTE = "gravacao"
DUR_CAMERA_MIN = 6.0  # a shorter segment has no time for a camera move to read as one
ZOOM_CAMERA = 1.06    # 6% is enough to breathe and never crops anything that matters
DUR_SECAO = 2.6       # how long the section chip stays on screen
DUR_TRANSICAO_SECAO = 0.25
TOL_ABERTURA = 1.2    # a section this close to a segment start is taken as opening that segment


# -------------------------------------------------------------------- helpers
def q(t: float, fps: float) -> int:
    return int(round(t * fps))


def amostras(frames: int, fps: float) -> int:
    return int(round(frames * SR / fps))


def fade(x: np.ndarray, n: int, subindo: bool) -> None:
    n = min(int(n), len(x))
    if n > 1:
        r = np.linspace(0, 1, n, dtype=np.float32)
        if subindo:
            x[:n] *= r
        else:
            x[len(x) - n:] *= r[::-1]


# -------------------------------------------------------------------- lines
def blocos(palavras: list, max_chars: int, max_linhas: int, gap: float = 0.7, max_words: int = 0) -> list:
    """Groups words into caption-sized blocks, breaking on sentence ends and long gaps.

    With `max_words` the block is counted in words instead of characters — the big one-or-two-word
    caption that carries a talking head."""
    if max_words > 0:
        fora, cur = [], []
        for w in palavras:
            cur.append(w)
            if len(cur) >= max_words or w["w"].endswith((".", "!", "?", "…")):
                fora.append(cur)
                cur = []
        if cur:
            fora.append(cur)
        return fora
    limite = max(12, max_chars * max_linhas)
    out, cur = [], []
    for i, w in enumerate(palavras):
        cur.append(w)
        texto = " ".join(x["w"] for x in cur)
        prox = palavras[i + 1] if i + 1 < len(palavras) else None
        fim_frase = w["w"].endswith((".", "!", "?", "…"))
        salto = prox is not None and prox["t"] - (w["t"] + w["d"]) >= gap
        if prox is None or fim_frase or salto or len(texto) + 1 + len(prox["w"]) > limite:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _fonte_da_legenda(p: Projeto, cap: dict, amb=None) -> dict:
    """`captions.font_file` -> the family name libass needs plus the directory to look in.

    Accepts a path inside the project (`assets/minha.ttf`) or the bare name of one of the fonts the
    plugin ships (`Barlow-Bold.ttf`). Either way the caption stops depending on whatever the
    machine happens to have installed."""
    cap = dict(cap)
    rel = str(cap.get("font_file") or "")
    if not rel:
        return cap
    caminho = p.raiz / rel
    if not caminho.exists() and amb is not None and "/" not in rel:
        empacotada = amb.tipografias / rel
        if empacotada.exists():
            caminho = empacotada
    if not caminho.exists():
        print(f"⚠ captions.font_file `{rel}` não existe (nem no projeto, nem entre as fontes do "
              f"plugin — rode `setup`) — usando `{cap.get('font')}`")
        return cap
    try:
        from PIL import ImageFont
        cap["fontname"] = ImageFont.truetype(str(caminho), 24).getname()[0]
    except (OSError, ValueError, ImportError) as e:
        print(f"⚠ não consegui ler o nome da família de `{rel}` ({e}) — usando `{cap.get('font')}`")
        return cap
    cap["fontsdir"] = str(caminho.parent)
    return cap


# -------------------------------------------------------------------- sections, focus, camera
def _secoes_por_segmento(secoes: list, segs: list, palavras: list | None, fps: float) -> dict:
    """Where each section lands: {segment index: [{"sec", "abre", "at"}]}.

    A section sitting within TOL_ABERTURA of a segment's start **opens** it — chip at frame 0 and
    a transition. One that falls deep inside a segment only places its chip there, because giving
    it a transition would mean cutting the segment in two, which the cut list did not ask for.

    The distinction matters: a cut usually starts the next segment a fraction of a second before
    the first word, so a section marked at that word lands just inside the PREVIOUS segment."""
    limites = []
    for sg in segs:
        try:
            limites.append((parse_tempo(sg.get("in", 0), palavras, fps),
                            parse_tempo(sg.get("out", 0), palavras, fps)))
        except AnchorError:
            limites.append((0.0, -1.0))
    fora: dict = {}
    abertos: set = set()
    for sec in secoes:
        try:
            at = parse_tempo(sec.get("at", 0), palavras, fps)
        except AnchorError:
            continue
        abre = next((i for i, (a, _) in enumerate(limites)
                     if a >= at - TOL_ABERTURA and i not in abertos), None)
        if abre is not None and limites[abre][0] - at <= TOL_ABERTURA:
            abertos.add(abre)
            fora.setdefault(abre, []).append({"sec": sec, "abre": True, "at": limites[abre][0]})
            continue
        alvo = next((i for i, (a, b) in enumerate(limites) if a - 1e-6 <= at <= b + 1e-6), None)
        if alvo is None:
            alvo = next((i for i, (a, _) in enumerate(limites) if a >= at), None)
        if alvo is not None:
            fora.setdefault(alvo, []).append({"sec": sec, "abre": False, "at": max(at, limites[alvo][0])})
    return fora


def _focos(p: Projeto, amb, segs: list, palavras: list | None, fps: float) -> dict:
    """{segment id: [x, y]} where a face is on screen — the focus of the default camera move."""
    trechos = []
    for i, sg in enumerate(segs):
        try:
            t0 = parse_tempo(sg.get("in", 0), palavras, fps)
            t1 = parse_tempo(sg.get("out", 0), palavras, fps)
        except AnchorError:
            continue
        trechos.append({"id": sg.get("id") or f"s{i + 1}",
                        "source": sg.get("source") or p.fonte_principal(),
                        "f0": q(t0, fps), "f1": q(t1, fps)})
    try:
        import enquadre
        return enquadre.rostos(p, amb, trechos)
    except Exception as e:  # optional finish: never let it stop a montage
        print(f"⚠ enquadramento automático indisponível ({e}) — a câmera fica parada")
        return {}


def _camera_do_segmento(sg: dict, cena: dict, foco, fps: float, palavras, n_auto: int, cfg: dict) -> dict:
    """What the cut asked for, or a gentle default when there is a person on screen.

    No face means a screen capture or a graphic, and a push there would crop away text — so the
    default is to leave it alone."""
    cam = dict(sg.get("camera") or {})
    if cam:
        if cam.get("at") is not None:
            try:
                cam["f"] = q(parse_tempo(cam["at"], palavras, fps), fps)
            except AnchorError:
                cam.pop("at", None)
        if not cam.get("focus") and foco:
            cam["focus"] = foco
        return cam
    if not cfg.get("auto", True):
        return {}
    zoom = float(cfg.get("zoom", ZOOM_CAMERA) or ZOOM_CAMERA)
    minima = float(cfg.get("dur_minima", DUR_CAMERA_MIN))
    if not foco or cena["mudo"] or cena["srcFrames"] / fps < minima:
        return {}
    if n_auto % 2:  # alternate, so two long segments in a row never move the same way
        return {"type": "pull", "from": zoom, "to": 1.0, "focus": foco, "auto": True}
    return {"type": "punch", "from": 1.0, "to": zoom, "focus": foco, "auto": True}


# -------------------------------------------------------------------- build
def construir(p: Projeto, amb=None) -> dict:
    cfg_r = p.cfg.get("render", {})
    fps = float(cfg_r.get("fps") or FORMATOS[FMT]["fps"])
    W = int(cfg_r.get("width") or FORMATOS[FMT]["width"])
    H = int(cfg_r.get("height") or FORMATOS[FMT]["height"])
    cap = _fonte_da_legenda(p, p.cfg["captions"], amb)
    tr_path = p.transcricao_path()
    if not tr_path.exists():
        raise SystemExit("sem transcrição — rode `transcrever` antes de `montar`")
    tr = json.loads(tr_path.read_text())
    palavras = tr["words"]
    fonte_da_transcricao = tr["fonte"]
    dados = p.corte()
    segs = dados.get("segments") or []
    if not segs:
        raise SystemExit("corte.json sem segmentos")
    look_projeto = p.cfg.get("look") or {}
    marca = p.cfg.get("brand") or {}
    cam_cfg = p.cfg.get("camera") or {}
    secoes = _secoes_por_segmento(dados.get("sections") or [], segs, palavras, fps)
    focos = _focos(p, amb, segs, palavras, fps) if cam_cfg.get("auto", True) else {}
    n_auto = 0

    audios: dict = {}

    def audio_de(nome: str) -> np.ndarray:
        if nome not in audios:
            cheio, _ = fonte.extrair_audio(p, nome)
            audios[nome] = fonte.ler_wav(cheio)
        return audios[nome]

    cenas, cortes, pos = [], [], 0
    for i, sg in enumerate(segs):
        nome = sg.get("source") or p.fonte_principal()
        t0 = parse_tempo(sg.get("in", 0), palavras, fps)
        t1 = parse_tempo(sg.get("out", 0), palavras, fps)
        f0, f1 = q(t0, fps), q(t1, fps)
        durF = max(1, f1 - f0)
        tin = dict(sg.get("transitionIn") or {"type": "none"})
        secs = secoes.get(i) or []
        abre = next((x["sec"] for x in secs if x["abre"]), None)
        # a section opens a subject: give it a transition unless the cut already chose one
        if abre and i > 0 and tin.get("type", "none") in ("none", "corte"):
            tin = {"type": abre.get("transition", "crossfade"),
                   "dur": float(abre.get("dur_transicao", DUR_TRANSICAO_SECAO))}
        ov = q(float(tin.get("dur", 0)), fps) if TRANSICOES_CORTE.get(tin.get("type", "none")) and i > 0 else 0
        ov = min(ov, durF - 1, cenas[-1]["durFrames"] - 1 if cenas else 0)
        inicio = max(0, pos - ov)
        cena = {
            "id": sg.get("id") or f"s{i + 1}",
            "kind": "corte",
            "source": nome,
            "srcFrom": f0, "srcFrames": durF,
            "srcT0": round(f0 / fps, 4), "srcT1": round((f0 + durF) / fps, 4),
            "from": inicio, "durFrames": durF,
            "t0": round(inicio / fps, 4), "t1": round((inicio + durF) / fps, 4),
            "transitionIn": {"type": tin.get("type", "none"), "frames": q(float(tin.get("dur", 0)), fps),
                             "overlapFrames": ov},
            "transitionOut": ({"type": sg["transitionOut"]["type"],
                               "frames": q(float(sg["transitionOut"].get("dur", 0)), fps)}
                              if sg.get("transitionOut") else None),
            # modo vídeo é relato falado: o leito padrão é o claro, não o dramático de ré menor
            "music": sg.get("music", "leve"),
            "mudo": bool(sg.get("mudo", False)),
            "ganho": float(sg.get("gain", 1.0)),
            "lines": [],
            "overlays": [],
        }
        if sg.get("note"):
            cena["note"] = sg["note"]
        cena["look"] = resolver_look(look_projeto, sg.get("look"))
        cena["camera"] = _camera_do_segmento(sg, cena, focos.get(cena["id"]), fps, palavras, n_auto, cam_cfg)
        if cena["camera"].get("auto"):
            n_auto += 1
        # transcript words that fall inside this slice of this source
        if nome == fonte_da_transcricao and not cena["mudo"]:
            dentro = [w for w in palavras if cena["srcT0"] - 1e-6 <= w["t"] < cena["srcT1"] - 1e-6]
        else:
            dentro = []
        for k, bl in enumerate(blocos(dentro, int(cap["max_chars"]), int(cap["max_lines"]),
                                      max_words=int(cap.get("max_words", 0) or 0))):
            desloc = cena["t0"] - cena["srcT0"]
            if k == 0 and cap.get("capitalizar", True) and bl and bl[0]["w"][:1].islower():
                bl = [{**bl[0], "w": bl[0]["w"][0].upper() + bl[0]["w"][1:]}] + bl[1:]
            l0 = bl[0]["t"] + desloc
            l1 = min(cena["t1"], bl[-1]["t"] + bl[-1]["d"] + desloc)
            ln = {
                "id": f"{cena['id']}_l{k + 1}", "speaker": FALANTE,
                "text": " ".join(w["w"] for w in bl), "screen": "", "screenText": " ".join(w["w"] for w in bl),
                "t": round(l0, 4), "dur": round(max(0.08, l1 - l0), 4),
                "from": q(l0, fps), "durFrames": max(1, q(l1, fps) - q(l0, fps)),
                "words": [{"w": w["w"], "t": round(w["t"] + desloc, 4), "f": q(w["t"] + desloc, fps),
                           "d": max(1, q(w["d"], fps)), "i": w["i"]} for w in bl],
            }
            ln["rel"] = ln["from"] - cena["from"]
            for w in ln["words"]:
                w["rel"] = w["f"] - cena["from"]
            cena["lines"].append(ln)
        if not cena["lines"]:  # b-roll / silent slice: one empty line so the score has a span to work with
            cena["lines"] = [{"id": f"{cena['id']}_l0", "speaker": FALANTE, "text": "", "screen": "",
                              "screenText": "", "t": cena["t0"], "dur": round(durF / fps, 4),
                              "from": cena["from"], "durFrames": durF, "rel": 0, "words": [], "vazia": True}]
        for j, ov_spec in enumerate(sg.get("overlays", [])):
            at = parse_tempo(ov_spec.get("at", 0), palavras, fps) + (cena["t0"] - cena["srcT0"])
            item = {k2: v for k2, v in ov_spec.items() if k2 != "at"}
            item.update({"id": f"{cena['id']}_o{j + 1}", "t": round(at, 4), "f": q(at, fps),
                         "rel": q(at, fps) - cena["from"], "durFrames": max(1, q(float(ov_spec.get("dur", 2)), fps))})
            cena["overlays"].append(item)
        for k, x in enumerate(secs):
            sec = x["sec"]
            rel = 0 if x["abre"] else max(0, q(x["at"], fps) - f0)
            cena["overlays"].insert(k, {
                "id": f"{cena['id']}_sec{k + 1}", "kind": "secao",
                "n": str(sec.get("n", "")), "title": sec["title"],
                "accent": sec.get("accent", "red"), "position": sec.get("position", "left"),
                "t": round((cena["from"] + rel) / fps, 4), "f": cena["from"] + rel, "rel": rel,
                "durFrames": max(1, q(float(sec.get("dur", DUR_SECAO)), fps)),
            })
        cortes.append({"cena": cena["id"], "source": nome, "srcFrom": f0, "frames": durF})
        cenas.append(cena)
        pos = inicio + durF

    total_frames = pos
    tf = float(marca.get("tela_final") or 0)
    if tf > 0 and cenas:  # the closing card: short, so only these frames go through Chrome
        ult = cenas[-1]
        rel = max(0, ult["durFrames"] - max(1, q(tf, fps)))
        ult["overlays"].append({
            "id": f"{ult['id']}_fim", "kind": "telaFinal",
            "title": marca.get("name") or p.titulo, "sub": marca.get("handle") or "",
            "accent": marca.get("color") or "red",
            "t": round((ult["from"] + rel) / fps, 4), "f": ult["from"] + rel, "rel": rel,
            "durFrames": ult["durFrames"] - rel,
        })
    tl = {
        "format": FMT, "modo": "video", "title": p.titulo, "fps": fps, "width": W, "height": H,
        "durationInFrames": total_frames, "duration": round(total_frames / fps, 4),
        "audio": f"audio/mix-{FMT}.wav", "images": 0,
        "palette": p.cfg["palette"], "captions": cap, "art": {},
        "look": resolver_look(look_projeto), "brand": marca,
        "sources": {n: str(p.fonte(n)) for n in p.sources()},
        "scenes": cenas, "sfx": [],
    }
    p.build.mkdir(parents=True, exist_ok=True)
    p.timeline_path(FMT).write_text(json.dumps(tl, ensure_ascii=False, indent=1))

    voz(p, tl, audio_de)
    legendas(p, tl)

    dur = tl["duration"]
    print(f"[{FMT}] {len(cenas)} segmento(s) · {int(dur // 60)}:{dur % 60:05.2f} = {total_frames} quadros @ {fps:g} fps")
    for c in cenas:
        falas = len([l for l in c["lines"] if not l.get("vazia")])
        cam = c.get("camera") or {}
        extra = f"  câmera={cam['type']}" if cam.get("type") else ""
        print(f"  {c['id']:10s} {c['t0']:7.2f} → {c['t1']:7.2f}  (fonte {c['srcT0']:7.2f}→{c['srcT1']:7.2f})  "
              f"{falas:2d} legenda(s)  entrada={c['transitionIn']['type']}{extra}"
              + (f"  · {c.get('note')}" if c.get("note") else ""))
    olhar = tl["look"]
    print(f"acabamento: preset `{olhar.get('preset')}`" + (f" · LUT {olhar['lut']}" if olhar.get("lut") else "")
          + f" · câmera automática em {sum(1 for c in cenas if (c.get('camera') or {}).get('auto'))} segmento(s)")
    return tl


# -------------------------------------------------------------------- voice
def voz(p: Projeto, tl: dict, audio_de) -> None:
    """The source audio cut to the same boundaries as the picture, joined with matching fades:
    a crossfade is a fade-out on the outgoing segment against the fade-in of the incoming one."""
    fps = tl["fps"]
    cenas = tl["scenes"]
    n = amostras(tl["durationInFrames"], fps)
    out = np.zeros(n + SR, np.float32)
    emenda = int(EMENDA * SR)
    sobe = [emenda] * len(cenas)
    desce = [emenda] * len(cenas)
    for i, cena in enumerate(cenas):
        ti = cena["transitionIn"]
        if ti.get("overlapFrames", 0) and i > 0:
            ov = amostras(ti["overlapFrames"], fps)
            sobe[i] = max(emenda, ov)
            desce[i - 1] = max(emenda, ov)
        elif ti["type"] == "fadeFromBlack":
            sobe[i] = max(emenda, amostras(ti["frames"], fps))
        to = cena.get("transitionOut")
        if to and to["type"] == "fadeToBlack":
            desce[i] = max(desce[i], amostras(to["frames"], fps))
    for i, cena in enumerate(cenas):
        larg = amostras(cena["srcFrames"], fps)
        trecho = np.zeros(larg, np.float32)
        if not cena["mudo"]:
            x = audio_de(cena["source"])
            a = amostras(cena["srcFrom"], fps)
            disp = x[a: a + larg]
            trecho[: len(disp)] = disp
            trecho *= cena["ganho"]
        fade(trecho, sobe[i], True)
        fade(trecho, desce[i], False)
        j = amostras(cena["from"], fps)
        m = min(len(trecho), len(out) - j)
        out[j: j + m] += trecho[:m]
    p.work.mkdir(parents=True, exist_ok=True)
    wavfile.write(p.work / f"voz-{FMT}.wav", SR, out[:n])
    print(f"voz editada: {p.work / f'voz-{FMT}.wav'} ({n / SR:.2f}s)")


# -------------------------------------------------------------------- captions
def ass_cor(hexa: str, alpha: int = 0) -> str:
    h = str(hexa).lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_tempo(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def dispor(palavras: list, max_chars: int, max_linhas: int) -> list:
    """Word indices per caption line (the layout is computed once, before any colour override)."""
    linhas, cur, larg = [], [], 0
    for i, w in enumerate(palavras):
        n = len(w)
        if cur and larg + 1 + n > max_chars:
            linhas.append(cur)
            cur, larg = [i], n
        else:
            cur.append(i)
            larg = larg + 1 + n if larg else n
    if cur:
        linhas.append(cur)
    if len(linhas) > max_linhas:  # rebalance into max_linhas roughly equal lines
        por = (len(palavras) + max_linhas - 1) // max_linhas
        linhas = [list(range(i, min(i + por, len(palavras)))) for i in range(0, len(palavras), por)]
    return linhas


def quebrar(texto: str, max_chars: int, max_linhas: int) -> str:
    ws = texto.split()
    return "\\N".join(" ".join(ws[i] for i in ln) for ln in dispor(ws, max_chars, max_linhas))


def legendas(p: Projeto, tl: dict) -> None:
    """saida/<slug>.srt (para subir no YouTube) e work/legendas.ass (queimada no render)."""
    cap = tl["captions"]
    falas = [l for c in tl["scenes"] for l in c["lines"] if not l.get("vazia")]
    # ---- srt
    cues = []
    for i, l in enumerate(falas):
        fim = l["t"] + l["dur"]
        prox = falas[i + 1]["t"] if i + 1 < len(falas) else fim + 2
        cues.append(f"{i + 1}\n{fmt_srt(l['t'])} --> {fmt_srt(min(fim + 0.4, prox - 0.03))}\n{wrap(l['text'])}\n")
    p.saida.mkdir(parents=True, exist_ok=True)
    p.srt(FMT).write_text("\n".join(cues), encoding="utf-8")
    # ---- ass
    align = {"bottom": 2, "center": 5, "top": 8}[cap.get("position", "bottom")]
    borda = 3 if cap.get("box") else 1
    fundo_alfa = round((1 - min(1.0, max(0.0, float(cap.get("bg_opacity", 0.55))))) * 255)
    margem = int(cap.get("margin", 100)) + int(cap.get("safe_bottom", 0) or 0)
    estilo = ",".join(str(v) for v in [
        "Legenda", cap.get("fontname") or cap.get("font", "DejaVu Sans"), int(cap["size"]),
        ass_cor(cap["color"]), ass_cor(cap["highlight"]), ass_cor("#000000"), ass_cor("#000000", fundo_alfa),
        -1 if cap.get("bold", True) else 0, 0, 0, 0, 100, 100, 0, 0,
        borda, float(cap.get("outline", 3)), float(cap.get("shadow", 0)),
        align, 60, 60, margem, 1])
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", "WrapStyle: 2", "ScaledBorderAndShadow: yes",
        f"PlayResX: {tl['width']}", f"PlayResY: {tl['height']}", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: {estilo}", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    destaque = ass_cor(cap["highlight"])
    base = ass_cor(cap["color"])
    mc, ml = int(cap["max_chars"]), int(cap["max_lines"])
    fade = max(0, int(cap.get("fade", 0) or 0))
    estufa = "\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)" if cap.get("pop") else ""
    caixa_alta = bool(cap.get("uppercase"))
    tx = (lambda v: v.upper()) if caixa_alta else (lambda v: v)

    def marcas(primeira: bool, ultima: bool) -> str:
        """Fade and pop belong to the BLOCK, not to every karaoke word — otherwise the caption
        would flicker once per spoken word."""
        t = []
        if fade and (primeira or ultima):
            t.append(f"\\fad({fade if primeira else 0},{fade if ultima else 0})")
        if primeira and estufa:
            t.append(estufa)
        return "{" + "".join(t) + "}" if t else ""

    for l in falas:
        fim_bloco = l["t"] + l["dur"]
        if not cap.get("karaoke", True) or not l["words"]:
            linhas.append(f"Dialogue: 0,{ass_tempo(l['t'])},{ass_tempo(fim_bloco)},Legenda,,0,0,0,,"
                          f"{marcas(True, True)}{tx(quebrar(l['text'], mc, ml))}")
            continue
        layout = dispor([w["w"] for w in l["words"]], mc, ml)
        uteis = [j for j in range(len(l["words"]))
                 if (l["words"][j + 1]["t"] if j + 1 < len(l["words"]) else fim_bloco)
                 - (l["words"][j]["t"] if j else l["t"]) >= 0.02]
        for j in uteis:
            w = l["words"][j]
            ini = w["t"] if j else l["t"]
            fim = l["words"][j + 1]["t"] if j + 1 < len(l["words"]) else fim_bloco
            texto = "\\N".join(" ".join(f"{{\\c{destaque}}}{tx(l['words'][k]['w'])}{{\\c{base}}}" if k == j
                                     else tx(l["words"][k]["w"]) for k in ln) for ln in layout)
            linhas.append(f"Dialogue: 0,{ass_tempo(ini)},{ass_tempo(fim)},Legenda,,0,0,0,,"
                          f"{marcas(j == uteis[0], j == uteis[-1])}{texto}")
    (p.work / "legendas.ass").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"legendas: {p.srt(FMT)} · {p.work / 'legendas.ass'} ({len(falas)} bloco(s))")


def gerar(p: Projeto, amb=None) -> dict:
    return construir(p, amb)
