"""Remotion bridge: stills for review (with automatic key-frame selection and contact sheets) and
the final render. Runs in the synced template inside the data dir, with the project's
.estudio/public as public dir and .estudio/timeline-<fmt>.json as input props."""
from __future__ import annotations

import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

from ambiente import Ambiente
from projeto import FORMATOS, Projeto


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def quadros_auto(tl: dict, cenas: set | None = None) -> list[tuple[int, str]]:
    """Mid-transition, the end of every line (all its text revealed) and the end of each scene."""
    out = []
    for i, sc in enumerate(tl["scenes"]):
        if cenas and sc["id"] not in cenas:
            continue
        F, D = sc["from"], sc["durFrames"]
        if i > 0 and sc["transitionIn"]["frames"] > 1:
            out.append((F + sc["transitionIn"]["frames"] // 2, f"{sc['id']} transição {sc['transitionIn']['type']}"))
        for ln in sc["lines"]:
            out.append((min(F + D - 1, ln["from"] + ln["durFrames"] - 1), f"{sc['id']} {ln['id']} ({ln['screen']})"))
        out.append((F + D - 8, f"{sc['id']} fim"))
    seen, res = set(), []
    for f, lab in sorted(out):
        f = max(0, min(tl["durationInFrames"] - 1, f))
        if f not in seen:
            seen.add(f)
            res.append((f, lab))
    return res


def stills(p: Projeto, amb: Ambiente, fmt: str, frames: list[int], rotulos: dict | None = None) -> list:
    amb.preparar_video(verbose=False)
    out_dir = p.quadros / fmt
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    cmd = ["node", "tools/stills.mjs", "--comp", FORMATOS[fmt]["comp"], "--props", str(p.timeline_path(fmt)),
           "--public", str(p.public), "--out", str(out_dir)] + [str(f) for f in frames]
    r = subprocess.run(cmd, cwd=amb.video, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falha ao renderizar quadros:\n{(r.stderr or r.stdout)[-3000:]}")
    return folhas(p, fmt, frames, rotulos or {})


def folhas(p: Projeto, fmt: str, frames: list[int], rotulos: dict) -> list:
    tl = json.loads(p.timeline_path(fmt).read_text())
    fps = tl["fps"]
    vertical = fmt == "shorts"
    tw, th = (360, 640) if vertical else (640, 360)
    cols, rows = (5, 2) if vertical else (3, 3)
    per = cols * rows
    f_lab = _font(15)
    outs = []
    for k in range(0, len(frames), per):
        chunk = frames[k:k + per]
        sheet = Image.new("RGB", (cols * tw, ((len(chunk) + cols - 1) // cols) * (th + 26)), (12, 12, 14))
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(chunk):
            x, y = (i % cols) * tw, (i // cols) * (th + 26)
            im = Image.open(p.quadros / fmt / f"{f:05d}.jpg").convert("RGB").resize((tw, th), Image.LANCZOS)
            sheet.paste(im, (x, y + 26))
            t = f / fps
            d.text((x + 6, y + 5), f"#{f} {int(t // 60)}:{t % 60:04.1f}  {rotulos.get(f, '')}"[:60], fill=(255, 225, 90), font=f_lab)
        out = p.quadros / f"folha_{fmt}_{k // per:02d}.jpg"
        sheet.save(out, quality=86)
        outs.append(out)
    print(f"[{fmt}] {len(frames)} quadros → {len(outs)} folha(s) em {p.quadros}")
    for o in outs:
        print(f"  {o}")
    return outs


def render(p: Projeto, amb: Ambiente, fmt: str) -> str:
    amb.preparar_video(verbose=False)
    rc = p.cfg["render"]
    out = p.mp4(fmt)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "remotion", "render", "src/index.ts", FORMATOS[fmt]["comp"], str(out),
           f"--props={p.timeline_path(fmt)}", f"--public-dir={p.public}", "--codec=h264", f"--crf={rc['crf']}",
           f"--x264-preset={rc.get('preset', 'slow')}", "--pixel-format=yuv420p", "--color-space=bt709",
           "--image-format=jpeg", "--jpeg-quality=95", "--audio-codec=aac", "--audio-bitrate=320k",
           f"--concurrency={rc['concurrency']}", "--log=info"]
    print(f"[{fmt}] renderizando {out} …", flush=True)
    subprocess.run(cmd, cwd=amb.video, check=True)
    return str(out)


# -------------------------------------------------------------------- video mode: overlay clips
def grupos_de_camadas(tl: dict, folga: int = 18) -> list:
    """Contiguous groups of overlays — only these frame ranges go through Chrome."""
    todos = []
    for sc in tl["scenes"]:
        for ov in sc.get("overlays", []):
            todos.append({**ov, "f": sc["from"] + ov["rel"] if "rel" in ov else ov["f"]})
    todos.sort(key=lambda o: o["f"])
    grupos = []
    for o in todos:
        fim = o["f"] + o["durFrames"]
        if grupos and o["f"] <= grupos[-1]["ate"] + folga:
            grupos[-1]["itens"].append(o)
            grupos[-1]["ate"] = max(grupos[-1]["ate"], fim)
        else:
            grupos.append({"de": o["f"], "ate": fim, "itens": [o]})
    return grupos


def camadas(p: Projeto, amb: Ambiente, tl: dict) -> list:
    """Renders one transparent ProRes 4444 clip per group; montagem.py lays them over the master."""
    import shutil

    grupos = grupos_de_camadas(tl)
    dest = p.work / "camadas"
    shutil.rmtree(dest, ignore_errors=True)
    saida_json = p.work / "camadas.json"
    if not grupos:
        saida_json.write_text("[]")
        print("sem overlays neste corte")
        return []
    amb.preparar_video(verbose=False)
    dest.mkdir(parents=True, exist_ok=True)
    publicas = p.public / "overlays"
    publicas.mkdir(parents=True, exist_ok=True)
    cap = tl.get("captions") or {}
    if cap.get("position", "bottom") == "bottom":
        reservado = (int(cap.get("margin", 100)) + int(cap.get("safe_bottom", 0) or 0)
                     + int(cap.get("size", 52)) * int(cap.get("max_lines", 2)) * 1.25)
        cap_base = round(min(0.45, reservado / max(1, tl["height"])), 4)
    else:
        cap_base = 0.06
    marca = dict(tl.get("brand") or {})
    if marca.get("logo"):  # the closing card and the sting draw it, so it has to be servable
        orig = p.raiz / str(marca["logo"])
        if orig.exists():
            shutil.copy2(orig, publicas / orig.name)
            marca["logo"] = f"overlays/{orig.name}"
        else:
            marca.pop("logo", None)
    fora = []
    for i, g in enumerate(grupos):
        itens = []
        for o in g["itens"]:
            item = {k: v for k, v in o.items() if k not in ("f", "t")}
            item["rel"] = o["f"] - g["de"]
            if o.get("kind") == "imagem" and o.get("file"):
                orig = p.raiz / o["file"]
                shutil.copy2(orig, publicas / orig.name)
                item["file"] = f"overlays/{orig.name}"
            itens.append(item)
        props = {"fps": tl["fps"], "width": tl["width"], "height": tl["height"],
                 "durationInFrames": g["ate"] - g["de"], "palette": tl.get("palette"),
                 "brand": marca, "capBase": cap_base, "overlays": itens}
        props_p = dest / f"grupo_{i:02d}.json"
        props_p.write_text(json.dumps(props, ensure_ascii=False))
        mov = dest / f"grupo_{i:02d}.mov"
        cmd = ["npx", "remotion", "render", "src/index.ts", "Camadas", str(mov),
               "--config=remotion.camadas.config.ts", f"--props={props_p}", f"--public-dir={p.public}",
               "--log=error", f"--concurrency={p.cfg['render'].get('concurrency', 4)}"]
        print(f"· camada {i + 1}/{len(grupos)}: quadros {g['de']}–{g['ate']} ({len(itens)} overlay(s)) …", flush=True)
        r = subprocess.run(cmd, cwd=amb.video, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"falha ao renderizar a camada {i}:\n{(r.stderr or r.stdout)[-3000:]}")
        fora.append({"from": g["de"], "ate": g["ate"], "arquivo": str(mov)})
    saida_json.write_text(json.dumps(fora, ensure_ascii=False, indent=1))
    print(f"{len(fora)} camada(s) → {saida_json}")
    return fora
