"""Video mode assembly: ffmpeg cuts the segments, joins them and burns the captions.

The timeline built by corte.py is already quantised to the output frame grid, so every clip here is
cut with `-frames:v`, which makes the frame count of the result exactly `durationInFrames` — the
check `qa` demands.

Three stages: one clip per segment body (and one per crossfade), a `concat` of all of them into
.estudio/work/master.mp4 (stream copy, instant), and a single final pass that lays the overlay clips
and the .ass captions over the master and muxes the mixed audio into saida/<slug>.mp4.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from ambiente import ffmpeg, recursos_ffmpeg
from projeto import Projeto

FMT = "main"
CRF_INTERMEDIARIO = 14

# Custom xfade expressions. Inside expr='…' a comma is literal, so `if()` and `mod()` are safe.
# X, Y = pixel; W, H = size; P = progress 0→1; A, B = the outgoing and incoming pixel.
EXPR_HAZARD = "if(lt((X/W)*0.7+(Y/H)*0.3, P*1.3-0.12+0.09*floor(mod((X+Y)/70,2))), B, A)"
EXPR_GLITCH = "if(gt(P*1.25, 0.12+abs(sin(floor(Y/36)*2.3))*0.85), B, A)"

# name in corte.json -> (xfade transition, custom expression, filter on the OUTGOING leg, filter on
# the INCOMING leg). The legs are a few frames long, so a constant filter already reads as movement;
# `{ZOOM:a:b}` is expanded into a real zoom over the transition (see _perna_filtro).
#
# `dissolve` deliberately maps to xfade's `fade`: what an editor calls a dissolve is a cross-fade.
# ffmpeg's own `dissolve` is a dithered random-pixel wipe, which over real footage looks like
# static — it is kept, honestly named, as `granulado`.
XFADE = {
    "crossfade": ("fade", None, "", ""),
    "dissolve": ("fade", None, "", ""),
    "granulado": ("dissolve", None, "", ""),
    "blur": ("hblur", None, "", ""),
    "pixel": ("pixelize", None, "", ""),
    "whipLeft": ("slideleft", None, "gblur=sigma=16:sigmaV=0", "gblur=sigma=16:sigmaV=0"),
    "whipRight": ("slideright", None, "gblur=sigma=16:sigmaV=0", "gblur=sigma=16:sigmaV=0"),
    # a zoom transition is the outgoing shot pushing in and the incoming one settling back
    "zoomPunch": ("fade", None, "{ZOOM:1.0:1.22},gblur=sigma=4", "{ZOOM:1.22:1.0},gblur=sigma=4"),
    "sliceH": ("hlslice", None, "", ""),
    "sliceV": ("vuslice", None, "", ""),
    "wipeDiagonal": ("diagtl", None, "", ""),
    "radial": ("radial", None, "", ""),
    "circleOpen": ("circleopen", None, "", ""),
    "dipBlack": ("fadeblack", None, "", ""),
    "dipWhite": ("fadewhite", None, "", ""),
    "glitch": ("custom", EXPR_GLITCH, "rgbashift=rh=7:bh=-7", "rgbashift=rh=-7:bh=7"),
    "filmBurn": ("fadewhite", None, "noise=alls=16:allf=t,eq=brightness=0.05",
                 "noise=alls=16:allf=t,eq=brightness=0.05"),
    "hazard": ("custom", EXPR_HAZARD, "", ""),
}
CORES_SAIDA = {"fadeToBlack": "black", "fadeToWhite": "white"}


def esc(caminho) -> str:
    """Escapes a path for use inside an ffmpeg filter argument."""
    return str(caminho).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")


# without these there is no video mode at all; the rest only costs finish, so it degrades
RECURSOS_ESSENCIAIS = ("libx264", "aac", "subtitles", "xfade")


def exigir_recursos():
    rec = recursos_ffmpeg()
    falta = [k for k in RECURSOS_ESSENCIAIS if not rec.get(k)]
    if falta:
        raise SystemExit(f"o ffmpeg disponível não tem {', '.join(falta)} — rode `estudio.py setup` "
                         "para baixar o ffmpeg estático")
    opcional = [k for k, v in rec.items() if not v and k not in RECURSOS_ESSENCIAIS]
    if opcional:
        print(f"⚠ este ffmpeg não tem {', '.join(opcional)} — o acabamento correspondente "
              f"({'LUT' if 'lut3d' in opcional else ''}{', vinheta' if 'vignette' in opcional else ''}"
              f"{', grão' if 'noise' in opcional else ''}{', câmera' if 'zoompan' in opcional else ''}"
              ") fica de fora")


def _tem(filtro: str) -> bool:
    return bool(recursos_ffmpeg().get(filtro, True))


def plano(tl: dict) -> list:
    """Clips to render, in output order: each segment body plus a clip per overlapping transition.

    An overlapping transition of `ov` frames eats `ov` frames from the end of the outgoing segment
    and `ov` from the start of the incoming one, so the totals still add up to durationInFrames.
    `overlapFrames` is written by corte.py and is 0 for a hard cut or a fade from black."""
    cenas = tl["scenes"]
    itens = []
    for i, c in enumerate(cenas):
        ov_in = c["transitionIn"].get("overlapFrames", 0)
        prox = cenas[i + 1] if i + 1 < len(cenas) else None
        ov_out = prox["transitionIn"].get("overlapFrames", 0) if prox else 0
        corpo = c["durFrames"] - ov_in - ov_out
        if corpo < 1:
            raise SystemExit(f"segmento `{c['id']}`: as transições ({ov_in + ov_out} quadros) consomem o "
                             f"segmento inteiro ({c['durFrames']} quadros) — encurte-as ou alongue o corte")
        entrada = c["transitionIn"]
        saida = c.get("transitionOut")
        inicio_corpo = c["srcFrom"] + ov_in
        cam = c.get("camera") or {}
        itens.append({
            "tipo": "corpo", "cena": c["id"], "source": c["source"],
            "srcFrom": inicio_corpo, "frames": corpo,
            "fadeIn": entrada["frames"] if entrada["type"] == "fadeFromBlack" else 0,
            "fadeOut": saida["frames"] if saida else 0,
            "fadeCor": (saida.get("color") or CORES_SAIDA.get(saida["type"], "black")) if saida else "black",
            "look": c.get("look") or {},
            "camera": cam,
            "camSnap": int(cam.get("f", 0)) - inicio_corpo,
        })
        if ov_out and prox:
            itens.append({
                "tipo": "transicao", "cena": f"{c['id']}~{prox['id']}", "frames": ov_out,
                "efeito": prox["transitionIn"]["type"],
                "source": c["source"], "srcFrom": c["srcFrom"] + c["durFrames"] - ov_out,
                "look": c.get("look") or {},
                "source2": prox["source"], "srcFrom2": prox["srcFrom"],
                "look2": prox.get("look") or {},
            })
    return itens


def _escala(w: int, h: int) -> str:
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")


def _par(v: float) -> int:
    """Nearest even integer (libx264 with yuv420p refuses odd sizes)."""
    return max(2, int(round(v / 2)) * 2)


def _camera(cam: dict, W: int, H: int, frames: int, fps: float, snap: int = 0) -> str:
    """The camera move inside a segment, as a linear filter chain.

    The clip is first scaled up to the TIGHTEST zoom of the move, so the widest framing still has
    1:1 detail and the closest one never invents pixels. `zoompan` with d=1 emits exactly one frame
    per input frame — the frame count, and therefore the sync, is untouched."""
    tipo = (cam or {}).get("type", "none")
    if tipo in ("", "none") or not _tem("zoompan"):
        return ""
    z0 = float(cam.get("from", 1.08 if tipo == "pull" else 1.0))
    z1 = float(cam.get("to", 1.0 if tipo == "pull" else 1.06))
    foco = cam.get("focus") or [0.5, 0.5]
    fx, fy = float(foco[0]), float(foco[1])
    zmax = max(z0, z1, 1.0)
    if tipo == "hold":  # fixed reframe: no animation, so a plain crop is exact and cheap
        lw, lh = _par(W * zmax), _par(H * zmax)
        return (f"scale={lw}:{lh}:flags=bicubic,"
                f"crop={W}:{H}:{(lw - W) * fx:.0f}:{(lh - H) * fy:.0f}")
    lw, lh = _par(W * zmax), _par(H * zmax)
    if tipo == "snap":
        k = max(0, min(frames - 1, int(snap)))
        z = f"if(gte(on,{k}),{z1:.5f},{z0:.5f})"
    else:  # punch / pull, with a smoothstep so it starts and ends still
        n = max(1, frames - 1)
        t = f"min(on/{n},1)"
        z = f"{z0:.5f}+({z1 - z0:.5f})*({t}*{t}*(3-2*{t}))"
    return (f"scale={lw}:{lh}:flags=bicubic,"
            f"zoompan=z='{z}':x='(iw-iw/zoom)*{fx:.4f}':y='(ih-ih/zoom)*{fy:.4f}':"
            f"d=1:s={W}x{H}:fps={fps:g}")


def _perna_filtro(spec: str, W: int, H: int, frames: int, fps: float) -> str:
    """A transition leg's filter, with `{ZOOM:z0:z1}` expanded into a move over the leg."""
    if "{ZOOM:" not in spec:
        return spec
    corpo = spec.split("{ZOOM:", 1)[1].split("}", 1)[0]
    z0, z1 = (float(v) for v in corpo.split(":"))
    zoom = _camera({"type": "punch", "from": z0, "to": z1, "focus": [0.5, 0.5]}, W, H, frames, fps)
    return spec.replace("{ZOOM:" + corpo + "}", zoom or "null")


def _look_graph(look: dict, raiz, ent: str, sai: str) -> str:
    """The picture finish, as a filtergraph fragment from label `ent` to label `sai`.

    Returns "" when there is nothing to do (preset `nenhum`), and the caller keeps using `ent`."""
    look = look or {}
    antes, depois = [], []
    if look.get("lut") and _tem("lut3d"):
        antes.append(f"lut3d=file='{esc(Path(raiz) / str(look['lut']))}'")
    eq = []
    for chave, neutro in (("contrast", 1.0), ("saturation", 1.0), ("brightness", 0.0), ("gamma", 1.0)):
        v = look.get(chave)
        if v is not None and abs(float(v) - neutro) > 1e-6:
            eq.append(f"{chave}={float(v):.4f}")
    if eq:
        antes.append("eq=" + ":".join(eq))
    temp = float(look.get("temp") or 0)
    if abs(temp) > 1e-6:  # positive = warmer, and a LOWER kelvin is what warms the picture
        antes.append(f"colortemperature=temperature={6500 - temp * 40:.0f}:mix=1:pl=0")
    if float(look.get("sharpen") or 0) > 1e-6:
        antes.append(f"unsharp=5:5:{float(look['sharpen']):.3f}:5:5:0")
    if float(look.get("chroma") or 0) > 1e-6:
        d = max(1, int(round(float(look["chroma"]))))
        antes.append(f"rgbashift=rh=-{d}:bh={d}")
    vinheta = float(look.get("vignette") or 0)
    if vinheta > 1e-6 and _tem("vignette"):
        depois.append(f"vignette=a={0.30 + 0.80 * min(1.0, vinheta):.4f}")
    grao = float(look.get("grain") or 0)
    if grao > 1e-6 and _tem("noise"):
        depois.append(f"noise=alls={grao:.1f}:allf=t+u")
    bloom = float(look.get("bloom") or 0)
    if not antes and not depois and bloom <= 1e-6:
        return ""
    if bloom <= 1e-6:
        return f"[{ent}]{','.join(antes + depois)}[{sai}]"
    # bloom: keep only the highlights, blur them wide and screen them back over the picture
    a = f"[{ent}]{','.join(antes)},split=2[bl_a][bl_b]" if antes else f"[{ent}]split=2[bl_a][bl_b]"
    b = "[bl_b]curves=all='0/0 0.55/0.02 0.8/0.35 1/1',gblur=sigma=20[bl_c]"
    c = f"[bl_a][bl_c]blend=all_mode=screen:all_opacity={min(1.0, bloom):.3f}"
    c += f",{','.join(depois)}[{sai}]" if depois else f"[{sai}]"
    return ";".join([a, b, c])


def _hash_curto(*partes) -> str:
    return hashlib.sha1(json.dumps(partes, sort_keys=True, default=str).encode()).hexdigest()[:8]


def _grafo_corpo(p: Projeto, it: dict, W: int, H: int, fps: float) -> tuple[str, str]:
    """Filtergraph of a segment body: framing, camera move, finish and fades. -> (grafo, rótulo)."""
    cadeia = [_escala(W, H), f"fps={fps:g}"]
    cam = _camera(it["camera"], W, H, it["frames"], fps, it.get("camSnap", 0))
    if cam:
        cadeia.append(cam)
    partes = [f"[0:v]{','.join(cadeia)}[q0]"]
    rot = "q0"
    olhar = _look_graph(it["look"], p.raiz, rot, "q1")
    if olhar:
        partes.append(olhar)
        rot = "q1"
    fades = []
    if it["fadeIn"]:
        fades.append(f"fade=t=in:st=0:d={min(it['fadeIn'], it['frames']) / fps:.4f}")
    if it["fadeOut"]:
        d = min(it["fadeOut"], it["frames"]) / fps
        fades.append(f"fade=t=out:st={max(0, it['frames'] / fps - d):.4f}:d={d:.4f}:color={it['fadeCor']}")
    if fades:
        partes.append(f"[{rot}]{','.join(fades)}[q2]")
        rot = "q2"
    return ";".join(partes), rot


def _grafo_transicao(p: Projeto, it: dict, W: int, H: int, fps: float) -> tuple[str, str]:
    """Filtergraph of a transition: each leg framed and graded with ITS OWN look, then blended."""
    d = it["frames"] / fps
    nome, expr, perna_a, perna_b = XFADE.get(it.get("efeito", "crossfade"), XFADE["crossfade"])
    partes, rotulos = [], []
    for k, (tag, look, perna) in enumerate((("a", it["look"], perna_a), ("b", it["look2"], perna_b))):
        base = f"{_escala(W, H)},fps={fps:g},trim=duration={d:.4f},setpts=PTS-STARTPTS"
        partes.append(f"[{k}:v]{base}[{tag}0]")
        rot = f"{tag}0"
        olhar = _look_graph(look, p.raiz, rot, f"{tag}1")
        if olhar:
            partes.append(olhar.replace("bl_", f"bl{tag}_"))
            rot = f"{tag}1"
        perna = _perna_filtro(perna, W, H, it["frames"], fps)
        if perna:
            partes.append(f"[{rot}]{perna}[{tag}2]")
            rot = f"{tag}2"
        rotulos.append(rot)
    alvo = f"transition={nome}" + (f":expr='{expr}'" if expr else "")
    partes.append(f"[{rotulos[0]}][{rotulos[1]}]xfade={alvo}:duration={d:.4f}:offset=0[v]")
    return ";".join(partes), "v"


def cortar(p: Projeto, tl: dict, forcar: bool = False) -> list:
    """One intermediate clip per item of the plan.

    The clip name carries a hash of the filtergraph, so changing the look, the camera or a
    transition produces a different name — a stale clip is never silently reused."""
    fps, W, H = tl["fps"], tl["width"], tl["height"]
    fontes = tl["sources"]
    dest = p.work / "cortes"
    if forcar and dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    itens = plano(tl)
    trabalho, saidas = [], []
    for k, it in enumerate(itens):
        if it["tipo"] == "corpo":
            grafo, rot = _grafo_corpo(p, it, W, H, fps)
        else:
            grafo, rot = _grafo_transicao(p, it, W, H, fps)
        h = _hash_curto(grafo, it["frames"], it["srcFrom"], it.get("srcFrom2"), it["source"], it.get("source2"))
        out = dest / f"{k:04d}_{it['tipo']}_{h}.mp4"
        saidas.append(out)
        trabalho.append((it, out, grafo, rot))
    validos = {o.name for o in saidas}
    for velho in dest.glob("*.mp4"):  # clipe de uma versão anterior do corte/look
        if velho.name not in validos:
            velho.unlink()
    for it, out, grafo, rot in trabalho:
        if out.exists() and not forcar:
            continue
        entradas = ["-ss", f"{it['srcFrom'] / fps:.6f}", "-i", fontes[it["source"]]]
        if it["tipo"] != "corpo":
            entradas += ["-ss", f"{it['srcFrom2'] / fps:.6f}", "-i", fontes[it["source2"]]]
        ffmpeg(*entradas, "-filter_complex", grafo, "-map", f"[{rot}]",
               "-frames:v", it["frames"], "-an",
               "-c:v", "libx264", "-crf", CRF_INTERMEDIARIO, "-preset", "veryfast",
               "-pix_fmt", "yuv420p", "-g", int(fps), str(out))
    total = sum(i["frames"] for i in itens)
    if total != tl["durationInFrames"]:
        raise SystemExit(f"plano de corte soma {total} quadros, timeline pede {tl['durationInFrames']}")
    print(f"[{FMT}] {len(itens)} clipe(s) de corte · {total} quadros")
    return saidas


def concatenar(p: Projeto, clipes: list) -> str:
    lista = p.work / "cortes.txt"
    lista.write_text("".join(f"file '{c}'\n" for c in clipes))
    master = p.work / "master.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(master))
    print(f"[{FMT}] master: {master}")
    return str(master)


def _cor_ffmpeg(hexa: str) -> str:
    h = str(hexa or "").lstrip("#")
    return f"0x{h}" if len(h) == 6 else "white"


def _marca_e_progresso(tl: dict, ent: str, sai: str, idx_logo: int | None) -> str:
    """Watermark and progress bar.

    Both last the whole video, which is exactly why they are ffmpeg and not Remotion overlays:
    a full-length overlay clip would push every single frame through Chrome."""
    marca = tl.get("brand") or {}
    H = tl["height"]
    dur = max(0.04, tl["durationInFrames"] / tl["fps"])
    antes, passos = [], []
    if idx_logo is not None:
        alt = max(8, int(H * float(marca.get("marca_altura", 0.06) or 0.06)))
        op = min(1.0, max(0.0, float(marca.get("marca_opacidade", 0.55) or 0)))
        m = int(H * 0.045)
        antes.append(f"[{idx_logo}:v]format=rgba,scale=-1:{alt}:flags=bicubic,"
                     f"colorchannelmixer=aa={op:.3f}[mk]")
        passos.append(("[mk]", f"overlay=W-w-{m}:{m}:format=auto"))
    if marca.get("progresso"):
        h = max(3, round(H / 270))
        passos.append(("", f"drawbox=x=0:y=ih-{h}:w='iw*min(t/{dur:.4f},1)':h={h}:"
                           f"color={_cor_ffmpeg(marca.get('color') or '#FFFFFF')}@0.92:t=fill"))
    if not passos:
        return ""
    partes, rot = list(antes), ent
    for k, (extra, filtro) in enumerate(passos):
        destino = sai if k == len(passos) - 1 else f"mp{k}"
        partes.append(f"[{rot}]{extra}{filtro}[{destino}]")
        rot = destino
    return ";".join(partes)


def finalizar(p: Projeto, tl: dict, camadas: list | None = None) -> str:
    """Watermark, progress bar, overlay clips, burned captions and mixed audio, in one encode."""
    fps = tl["fps"]
    rc = p.cfg["render"]
    master = p.work / "master.mp4"
    audio = p.audio / f"mix-{FMT}.wav"
    if not audio.exists():
        raise SystemExit(f"{audio} não existe — rode `mix` antes do render")
    entradas = ["-i", str(master), "-i", str(audio)]
    partes, atual = [], "0:v"
    for i, cam in enumerate(camadas or []):
        entradas += ["-i", str(cam["arquivo"])]
    marca = tl.get("brand") or {}
    idx_logo = None
    logo = p.raiz / str(marca.get("logo") or "")
    if marca.get("logo") and marca.get("marca", True) and logo.exists():
        entradas += ["-i", str(logo)]
        idx_logo = 2 + len(camadas or [])
    # under the overlays and under the captions: a full-screen card should cover the watermark
    mp = _marca_e_progresso(tl, atual, "mp", idx_logo)
    if mp:
        partes.append(mp)
        atual = "mp"
    for i, cam in enumerate(camadas or []):
        # the clip is padded with transparent frames up to its start: `-itsoffset` would make overlay
        # drop main frames while it waits for the second input, and the frame count has to match
        partes.append(f"[{i + 2}:v]format=rgba,setpts=PTS-STARTPTS,"
                      f"tpad=start_duration={cam['from'] / fps:.6f}:start_mode=add:color=black@0.0[c{i}]")
        partes.append(f"[{atual}][c{i}]overlay=0:0:eof_action=pass:repeatlast=0:format=auto[v{i}]")
        atual = f"v{i}"
    ass = p.work / "legendas.ass"
    if ass.exists():
        dir_fontes = (tl.get("captions") or {}).get("fontsdir")
        extra = f":fontsdir='{esc(dir_fontes)}'" if dir_fontes else ""
        partes.append(f"[{atual}]subtitles='{esc(ass)}'{extra}[vout]")
        atual = "vout"
    filtro = ";".join(partes)
    out = p.mp4(FMT)
    out.parent.mkdir(parents=True, exist_ok=True)
    args = list(entradas)
    if filtro:
        args += ["-filter_complex", filtro, "-map", f"[{atual}]"]
    else:
        args += ["-map", "0:v"]
    args += ["-map", "1:a", "-frames:v", tl["durationInFrames"],
             "-c:v", "libx264", "-crf", rc["crf"], "-preset", rc.get("preset", "slow"),
             "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(out)]
    print(f"[{FMT}] render final → {out} …", flush=True)
    ffmpeg(*args)
    print(f"[{FMT}] pronto: {out}")
    return str(out)


def camadas_atualizadas(p: Projeto, amb, tl: dict) -> list:
    """Overlay clips, re-rendered when the timeline is newer than them."""
    import remotion
    cam_json = p.work / "camadas.json"
    tem = any(sc.get("overlays") for sc in tl["scenes"])
    if not tem:
        return []
    if cam_json.exists() and cam_json.stat().st_mtime >= p.timeline_path(FMT).stat().st_mtime:
        return json.loads(cam_json.read_text())
    return remotion.camadas(p, amb, tl)


def render(p: Projeto, amb=None, forcar: bool = False) -> str:
    exigir_recursos()
    tl = json.loads(p.timeline_path(FMT).read_text())
    camadas = camadas_atualizadas(p, amb, tl) if amb else []
    clipes = cortar(p, tl, forcar=forcar)
    concatenar(p, clipes)
    return finalizar(p, tl, camadas)


# -------------------------------------------------------------------- review frames
def quadros_auto(tl: dict, cenas: set | None = None) -> list:
    """Mid-transition, the end of every caption block and one frame late in each segment."""
    out = []
    for i, c in enumerate(tl["scenes"]):
        if cenas and c["id"] not in cenas:
            continue
        F, D = c["from"], c["durFrames"]
        if i > 0 and c["transitionIn"]["frames"] > 1:
            out.append((F + c["transitionIn"]["frames"] // 2, f"{c['id']} transição {c['transitionIn']['type']}"))
        for ln in c["lines"]:
            if ln.get("vazia"):
                continue
            out.append((min(F + D - 1, ln["from"] + ln["durFrames"] - 1), f"{c['id']} {ln['id']}"))
        out.append((max(F, F + D - 8), f"{c['id']} fim"))
    vistos, res = set(), []
    for f, lab in sorted(out):
        f = max(0, min(tl["durationInFrames"] - 1, f))
        if f not in vistos:
            vistos.add(f)
            res.append((f, lab))
    return res


def quadros(p: Projeto, frames: list, rotulos: dict) -> list:
    """Stills straight out of the finished mp4 (or the master, when there is no final render yet)."""
    import remotion
    tl = json.loads(p.timeline_path(FMT).read_text())
    src = p.mp4(FMT) if p.mp4(FMT).exists() else p.work / "master.mp4"
    if not src.exists():
        raise SystemExit("nem o vídeo final nem o master existem — rode `render`")
    out_dir = p.quadros / FMT
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    ass = p.work / "legendas.ass"
    legenda_viva = src == p.work / "master.mp4" and ass.exists()
    dir_fontes = (tl.get("captions") or {}).get("fontsdir")
    sub = f"subtitles='{esc(ass)}'" + (f":fontsdir='{esc(dir_fontes)}'" if dir_fontes else "")
    for f in frames:
        vf = [sub] if legenda_viva else []
        ffmpeg("-ss", f"{f / tl['fps']:.6f}", "-i", str(src), "-frames:v", 1,
               *(["-vf", ",".join(vf)] if vf else []), "-q:v", 2, str(out_dir / f"{f:05d}.jpg"))
    print(f"[{FMT}] quadros de {src.name}")
    return remotion.folhas(p, FMT, frames, rotulos)
