"""Post-render QA: stream specs vs. the timeline, faststart, loudness, and contact sheets sampled at
exact frame numbers."""
from __future__ import annotations

import json
import re
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw

from ambiente import ffmpeg, ffprobe_json
from projeto import Projeto

# below these the picture reads as washed out — a warning, never a failure: a deliberately flat
# look is a legitimate choice, and only a person can say which it is
CONTRASTE_MINIMO = 0.34
SATURACAO_MINIMA = 0.06


def top_atoms(path) -> list[str]:
    atoms = []
    with open(path, "rb") as f:
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size, kind = struct.unpack(">I4s", hdr)
            if size == 1:
                size = struct.unpack(">Q", f.read(8))[0]
                f.seek(size - 16, 1)
            elif size == 0:
                atoms.append(kind.decode("latin1"))
                break
            else:
                f.seek(size - 8, 1)
            atoms.append(kind.decode("latin1"))
    return atoms


def medir_imagem(frames: list) -> dict:
    """Mean luma, contrast (the p2–p98 spread) and saturation over the sampled frames."""
    lum, con, sat = [], [], []
    for fp in frames:
        a = np.asarray(Image.open(fp).convert("RGB"), dtype=np.float32) / 255.0
        y = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        lo, hi = np.percentile(y, 2), np.percentile(y, 98)
        lum.append(float(y.mean()))
        con.append(float(hi - lo))
        sat.append(float((a.max(axis=2) - a.min(axis=2)).mean()))
    if not lum:
        return {}
    return {"luminancia": round(float(np.mean(lum)), 3),
            "contraste": round(float(np.mean(con)), 3),
            "saturacao": round(float(np.mean(sat)), 3)}


def conferir(p: Projeto, fmt: str, every: float = 4.0) -> dict:
    src = p.mp4(fmt)
    if not src.exists():
        raise FileNotFoundError(f"{src} não existe — rode `estudio.py render --formato {fmt}`")
    tl = json.loads(p.timeline_path(fmt).read_text())
    info = ffprobe_json(src)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = map(int, v["r_frame_rate"].split("/"))
    atoms = top_atoms(src)
    log = ffmpeg("-i", str(src), "-map", "0:a", "-af", "ebur128=peak=true", "-f", "null", "-", quiet=False)
    summ = log[log.rfind("Summary:"):]
    I = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    tp = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
    lufs_alvo = p.cfg["mix"]["lufs"]
    r = {
        "arquivo": str(src),
        "tamanho_mb": round(int(info["format"]["size"]) / 1e6, 1),
        "video": f"{v['codec_name']} {v.get('profile')} {v['width']}x{v['height']} {num / den:g} fps {v['pix_fmt']}",
        "audio": f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']} ch" if a else "sem áudio",
        "duracao_s": round(float(info["format"]["duration"]), 3),
        "quadros": int(v.get("nb_frames", 0)),
        "lufs": float(I.group(1)) if I else None,
        "pico_real_dbtp": float(tp.group(1)) if tp else None,
        "faststart": "moov" in atoms and "mdat" in atoms and atoms.index("moov") < atoms.index("mdat"),
    }
    checks = {
        "resolução": (v["width"], v["height"]) == (tl["width"], tl["height"]),
        "fps": abs(num / den - tl["fps"]) < 0.01,
        "quadros = timeline": r["quadros"] == tl["durationInFrames"],
        "yuv420p": v["pix_fmt"] == "yuv420p",
        "áudio AAC 48 kHz": bool(a) and a["codec_name"] == "aac" and a["sample_rate"] == "48000",
        f"loudness {lufs_alvo:g} ±1 LUFS": r["lufs"] is not None and abs(r["lufs"] - lufs_alvo) <= 1.0,
        "pico real ≤ -1 dBTP": r["pico_real_dbtp"] is not None and r["pico_real_dbtp"] <= -0.9,
        "faststart": r["faststart"],
    }
    if fmt == "shorts":
        checks["Shorts ≤ 60 s"] = r["duracao_s"] <= 60.0
    r["checks"] = checks
    # contact sheets at exact frames 0, N, 2N…
    out = p.qa / fmt
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    step = max(1, round(every * num / den))
    ffmpeg("-i", str(src), "-vf", f"select='not(mod(n\\,{step}))',scale=480:-2", "-fps_mode", "vfr", "-q:v", "3", str(out / "f_%03d.jpg"))
    frames = sorted(out.glob("f_*.jpg"))
    sheets = []
    if frames:
        w, h = Image.open(frames[0]).size
        cols = 6 if w > h else 8
        per = cols * (3 if w > h else 2)
        for k in range(0, len(frames), per):
            chunk = frames[k:k + per]
            rows = (len(chunk) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * w, rows * h), "black")
            d = ImageDraw.Draw(sheet)
            for i, fp in enumerate(chunk):
                x, y = (i % cols) * w, (i // cols) * h
                sheet.paste(Image.open(fp), (x, y))
                t = (k + i) * step * den / num
                d.text((x + 8, y + 6), f"{int(t // 60)}:{t % 60:04.1f}", fill=(255, 255, 0))
            path = p.qa / f"folha_{fmt}_{k // per:02d}.jpg"
            sheet.save(path, quality=85)
            sheets.append(str(path))
    r["folhas"] = sheets
    r["imagem"] = medir_imagem(frames)
    avisos = []
    if r["imagem"]:
        if r["imagem"]["contraste"] < CONTRASTE_MINIMO:
            avisos.append(f"imagem chapada (contraste {r['imagem']['contraste']:.2f}) — veja "
                          f"`projeto.json → look` (preset, contrast, vignette)")
        if r["imagem"]["saturacao"] < SATURACAO_MINIMA:
            avisos.append(f"imagem sem cor (saturação {r['imagem']['saturacao']:.2f}) — veja "
                          f"`projeto.json → look.saturation`")
    r["avisos"] = avisos
    print(json.dumps({k: v for k, v in r.items() if k != "folhas"}, ensure_ascii=False, indent=1))
    for s in sheets:
        print("folha:", s)
    for a in avisos:
        print("⚠", a)
    ok = all(checks.values())
    print(("✓ tudo certo" if ok else "✗ falhou: " + ", ".join(k for k, v in checks.items() if not v)))
    return r
