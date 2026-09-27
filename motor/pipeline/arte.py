"""Art prep: 4x upscale (Real-ESRGAN, Lanczos fallback), crops with text inpainting, glow/bg/alpha
versions, depth maps (Depth Anything V2), procedural textures, coordinate grids and crop previews."""
from __future__ import annotations

import json
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ambiente import Ambiente
from projeto import Projeto


def _font(size: int):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


# -------------------------------------------------------------------- upscale
def ampliar(p: Projeto, amb: Ambiente, forcar: bool = False):
    p.up.mkdir(parents=True, exist_ok=True)
    scale = int(p.arte().get("scale", 4))
    usar_ia = amb.realesrgan.exists() and scale == 4
    for i, src in enumerate(p.imagens(), 1):
        out = p.up / f"{i}.png"
        if out.exists() and not forcar and out.stat().st_mtime >= src.stat().st_mtime:
            continue
        ok = False
        if usar_ia:
            # small tiles: integrated GPUs time out (VK_ERROR_DEVICE_LOST) with the default tile size
            r = subprocess.run([str(amb.realesrgan), "-i", str(src), "-o", str(out), "-n", "realesrgan-x4plus",
                                "-s", "4", "-t", "64", "-m", str(amb.realesrgan_modelos)], capture_output=True, text=True)
            ok = r.returncode == 0 and out.exists()
            if not ok:
                print(f"  Real-ESRGAN falhou na imagem {i} ({(r.stderr.strip().splitlines() or ['?'])[-1][:100]}); usando Lanczos")
        if not ok:
            im = Image.open(src).convert("RGB")
            im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
            im = im.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=2))
            im.save(out)
        print(f"imagem {i}: {src.name} → {out.name} ({'Real-ESRGAN' if ok else 'Lanczos'})")


# -------------------------------------------------------------------- grids
def grades(p: Projeto):
    """Coordinate grids over the ORIGINAL images (crop boxes use original pixel units)."""
    p.grades.mkdir(parents=True, exist_ok=True)
    outs = []
    for i, src in enumerate(p.imagens(), 1):
        im = Image.open(src).convert("RGB")
        W, H = im.size
        k = max(1, int(np.ceil(1600 / max(W, H))))
        big = im.resize((W * k, H * k), Image.LANCZOS)
        pad = 34
        canvas = Image.new("RGB", (big.width + pad, big.height + pad), (18, 18, 22))
        canvas.paste(big, (pad, pad))
        d = ImageDraw.Draw(canvas, "RGBA")
        f = _font(13)
        step = 10 if max(W, H) <= 1200 else 20
        for x in range(0, W + 1, step):
            major = x % 50 == 0
            d.line([(pad + x * k, pad), (pad + x * k, pad + H * k)], fill=(255, 255, 0, 150 if major else 45), width=1)
            if x % 50 == 0:
                d.text((pad + x * k + 2, 2), str(x), fill=(255, 255, 0), font=f)
        for y in range(0, H + 1, step):
            major = y % 50 == 0
            d.line([(pad, pad + y * k), (pad + W * k, pad + y * k)], fill=(0, 255, 255, 150 if major else 45), width=1)
            if y % 50 == 0:
                d.text((2, pad + y * k + 2), str(y), fill=(0, 255, 255), font=f)
        out = p.grades / f"grade_{i}.jpg"
        canvas.save(out, quality=88)
        outs.append(out)
        print(f"grade {i}: {out} (imagem {W}×{H}, ampliada {k}× para leitura)")
    return outs


# -------------------------------------------------------------------- crops
def text_mask(img_bgr: np.ndarray, rect) -> np.ndarray:
    """Mask of letter pixels inside rect (upscaled coords): bright or saturated pixels that stand out
    from a median-estimated background."""
    x0, y0, x1, y1 = rect
    pad = 40
    H, W = img_bgr.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    region = img_bgr[Y0:Y1, X0:X1]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV).astype(np.float32) / 255.0
    lum = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    bg = cv2.medianBlur((lum * 255).astype(np.uint8), 61).astype(np.float32) / 255.0
    m = ((lum - bg) > 0.10) | ((hsv[..., 1] * hsv[..., 2]) > 0.28) | (lum > 0.55)
    m = m.astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((9, 9), np.uint8))
    full = np.zeros((H, W), np.uint8)
    sub = full[Y0:Y1, X0:X1]
    sub[(y0 - Y0):(y1 - Y0), (x0 - X0):(x1 - X0)] = m[(y0 - Y0):(y1 - Y0), (x0 - X0):(x1 - X0)]
    return full


def _alpha_luma(crop_bgr: np.ndarray) -> Image.Image:
    """Emblem on a dark background -> RGBA (alpha from luminance, corners dropped)."""
    sig = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    lum = sig.max(axis=2)
    alpha = np.clip((lum - 0.09) / 0.28, 0, 1)
    yy, xx = np.mgrid[0:alpha.shape[0], 0:alpha.shape[1]]
    se = np.abs((xx / alpha.shape[1] - 0.5) * 2) ** 6 + np.abs((yy / alpha.shape[0] - 0.5) * 2) ** 6
    alpha *= np.clip((1.0 - se) / 0.35, 0, 1)  # drop stray frame marks in the corners
    rgb = np.clip(sig / np.maximum(lum[..., None], 1e-3), 0, 1)  # un-premultiply the dark background
    return Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")


def recortes(p: Projeto):
    p.art.mkdir(parents=True, exist_ok=True)
    p.work.mkdir(parents=True, exist_ok=True)
    arte = p.arte()
    S = int(arte.get("scale", 4))
    meta, cache = {}, {}
    for name, spec in arte.get("crops", {}).items():
        i = spec["image"]
        if i not in cache:
            up = p.up / f"{i}.png"
            if not up.exists():
                raise FileNotFoundError(f"{up} não existe — rode a ampliação (`estudio.py arte --so ampliar`)")
            cache[i] = cv2.imread(str(up), cv2.IMREAD_COLOR)
        img = cache[i].copy()
        mask = np.zeros(img.shape[:2], np.uint8)
        for r in spec.get("text", []):
            mask |= text_mask(img, tuple(int(v * S) for v in r))
        for r in spec.get("fill", []):
            x0, y0, x1, y1 = (int(v * S) for v in r)
            mask[y0:y1, x0:x1] = 255
        if mask.any():
            img = cv2.inpaint(img, mask, 12, cv2.INPAINT_TELEA)
            # soften the inpainted area a bit so smears read as haze, not streaks
            blur = cv2.GaussianBlur(img, (0, 0), 6)
            soft = cv2.GaussianBlur(mask, (0, 0), 8).astype(np.float32)[..., None] / 255.0
            img = (img * (1 - soft) + blur * soft).astype(np.uint8)
        cv2.imwrite(str(p.work / f"mask_{name}.png"), mask)
        x0, y0, x1, y1 = (int(v * S) for v in spec["box"])
        crop = img[y0:y1, x0:x1]
        cv2.imwrite(str(p.art / f"{name}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 93])
        alpha = spec.get("alpha") == "luma"
        if alpha:
            _alpha_luma(crop).save(p.art / f"{name}.png")
        depth = bool(spec.get("depth", not alpha))
        meta[name] = {"w": int(crop.shape[1]), "h": int(crop.shape[0]), "img": i, "depth": depth, "alpha": alpha}
        print(f"{name}: {crop.shape[1]}×{crop.shape[0]}" + (" (alfa)" if alpha else ""))
        # glow: blurred + brightened version (screen-blended & pulsed in the video)
        pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        small = pil.resize((max(1, pil.width // 2), max(1, pil.height // 2)), Image.LANCZOS)
        g = np.asarray(small.filter(ImageFilter.GaussianBlur(14))).astype(np.float32) / 255.0
        g = np.clip((g ** 1.6) * 1.8, 0, 1)
        Image.fromarray((g * 255).astype(np.uint8)).save(p.art / f"{name}_glow.jpg", quality=88)
    # blurred, darkened full images for ambient backgrounds
    for i, _ in enumerate(p.imagens(), 1):
        pil = Image.open(p.up / f"{i}.png").convert("RGB")
        w = 960
        h = round(pil.height * w / pil.width)
        b = pil.resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(28))
        Image.fromarray((np.asarray(b).astype(np.float32) * 0.5).astype(np.uint8)).save(p.art / f"bg_{i}.jpg", quality=85)
    (p.art / "art.json").write_text(json.dumps(meta, indent=1))
    return meta


def previa(p: Projeto):
    """Contact sheet: each crop next to its source region with the inpainted pixels in red."""
    meta = json.loads((p.art / "art.json").read_text())
    arte = p.arte()
    S = int(arte.get("scale", 4))
    tiles = []
    f = _font(18)
    for name, m in meta.items():
        spec = arte["crops"][name]
        crop = Image.open(p.art / f"{name}.jpg").convert("RGB")
        src = Image.open(p.imagem(spec["image"])).convert("RGB")
        x0, y0, x1, y1 = spec["box"]
        region = src.crop((x0, y0, x1, y1)).resize(crop.size, Image.LANCZOS)
        th = 420
        a = crop.resize((max(1, round(crop.width * th / crop.height)), th), Image.LANCZOS)
        b = region.resize(a.size, Image.LANCZOS)
        mk = p.work / f"mask_{name}.png"
        if mk.exists():  # inpainted pixels: cyan tint + outline (stands out on red/dark art)
            mask = Image.open(mk).convert("L").crop((int(x0 * S), int(y0 * S), int(x1 * S), int(y1 * S))).resize(a.size)
            b = Image.composite(Image.blend(b, Image.new("RGB", a.size, (0, 255, 220)), 0.45), b, mask)
            cnts, _ = cv2.findContours((np.asarray(mask) > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            arr = np.ascontiguousarray(np.asarray(b)[..., ::-1])
            cv2.drawContours(arr, cnts, -1, (220, 255, 0), 2)
            b = Image.fromarray(arr[..., ::-1])
        tile = Image.new("RGB", (a.width * 2 + 30, th + 58), (22, 22, 26))
        tile.paste(b, (0, 58))
        tile.paste(a, (a.width + 30, 58))
        d = ImageDraw.Draw(tile)
        d.text((6, 6), f"{name} · imagem {spec['image']} · {m['w']}×{m['h']}", fill=(255, 230, 120), font=f)
        d.text((6, 30), f"caixa {spec['box']} · esquerda: original (ciano = apagado) · direita: final", fill=(170, 170, 170), font=_font(14))
        tiles.append(tile)
    if not tiles:
        return []
    outs, sheet_w = [], 1900
    rows, row, x = [], [], 0
    for t in tiles:
        tt = t if t.width <= sheet_w else t.resize((sheet_w, round(t.height * sheet_w / t.width)))
        if x + tt.width > sheet_w and row:
            rows.append(row)
            row, x = [], 0
        row.append(tt)
        x += tt.width + 10
    rows.append(row)
    per_sheet = 3
    for k in range(0, len(rows), per_sheet):
        chunk = rows[k:k + per_sheet]
        H = sum(max(t.height for t in r) + 10 for r in chunk)
        sheet = Image.new("RGB", (sheet_w, H), (10, 10, 12))
        y = 0
        for r in chunk:
            x = 0
            for t in r:
                sheet.paste(t, (x, y))
                x += t.width + 10
            y += max(t.height for t in r) + 10
        out = p.build / f"arte_previa_{k // per_sheet}.jpg"
        sheet.save(out, quality=86)
        outs.append(out)
        print(f"prévia: {out}")
    return outs


# -------------------------------------------------------------------- depth
def profundidade(p: Projeto, amb: Ambiente, forcar: bool = False):
    meta = json.loads((p.art / "art.json").read_text())
    todo = [n for n, m in meta.items() if m.get("depth")]
    if not amb.modelo_profundidade.exists():
        print("modelo de profundidade ausente: sem paralaxe 2.5D (rode `estudio.py setup`)")
        for n in todo:
            meta[n]["depth"] = False
        (p.art / "art.json").write_text(json.dumps(meta, indent=1))
        return
    import onnxruntime as ort
    sess = None
    mean = np.array([0.485, 0.456, 0.406], np.float32)
    std = np.array([0.229, 0.224, 0.225], np.float32)
    for name in todo:
        out = p.art / f"{name}_depth.png"
        src = p.art / f"{name}.jpg"
        if out.exists() and not forcar and out.stat().st_mtime >= src.stat().st_mtime:
            continue
        if sess is None:
            sess = ort.InferenceSession(str(amb.modelo_profundidade), providers=["CPUExecutionProvider"])
            inp = sess.get_inputs()[0]
        pil = Image.open(src).convert("RGB")
        W, H = pil.size
        scale = 518 / min(W, H)  # short side 518, both multiples of 14
        tw, th = int(round(W * scale / 14)) * 14, int(round(H * scale / 14)) * 14
        x = np.asarray(pil.resize((tw, th), Image.BICUBIC)).astype(np.float32) / 255.0
        x = ((x - mean) / std).transpose(2, 0, 1)[None]
        d = np.squeeze(sess.run(None, {inp.name: x})[0]).astype(np.float32)
        lo, hi = np.percentile(d, 2), np.percentile(d, 98)
        d = np.clip((d - lo) / max(1e-6, hi - lo), 0, 1)
        d = cv2.GaussianBlur(d, (0, 0), 2.5)
        d = np.clip(cv2.resize(d, (W // 2, H // 2), interpolation=cv2.INTER_CUBIC), 0, 1)
        rgb = np.stack([d, d, np.full_like(d, 0.5)], -1)  # R=G=depth, B=0.5 (neutral axis for feDisplacementMap)
        Image.fromarray((rgb * 255).round().astype(np.uint8)).save(out)
        print(f"profundidade {name}: {W // 2}×{H // 2}")


# -------------------------------------------------------------------- procedural textures
def spectral_noise(h, w, beta, rng):
    """Tileable fractal noise via 1/f^beta spectrum."""
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    amp = 1.0 / f ** (beta / 2.0)
    amp[0, 0] = 0.0
    phase = rng.uniform(0, 2 * np.pi, (h, w))
    n = np.real(np.fft.ifft2(amp * np.exp(1j * phase)))
    n = (n - n.min()) / (n.max() - n.min())
    return n.astype(np.float32)


def noise1d(n, scale, rng, octaves=4):
    out = np.zeros(n, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        k = max(2, int(n / scale * (2 ** o)) + 2)
        pts = rng.uniform(-1, 1, k)
        out += amp * np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
        tot += amp
        amp *= 0.5
    return out / tot


def make_brush(path, rng, W=1800, H=380):
    y = np.arange(H)[:, None].astype(np.float32)
    x = np.arange(W)[None, :].astype(np.float32)
    top = 78 + 16 * noise1d(W, 260, rng)[None, :]
    bot = H - 78 + 16 * noise1d(W, 260, rng)[None, :]
    rows = H  # ragged ends: per-row start/end with streaky lengths (dry brush)
    start = 70 + 150 * np.abs(noise1d(rows, 9, rng, 3))[:, None] + 60 * rng.random((rows, 1)) ** 3
    end = W - 70 - 220 * np.abs(noise1d(rows, 9, rng, 3))[:, None] - 90 * rng.random((rows, 1)) ** 3
    a = ((y > top) & (y < bot) & (x > start) & (x < end)).astype(np.float32)
    bristle = 0.78 + 0.28 * noise1d(rows, 3, rng, 3)[:, None]
    drift = 0.9 + 0.1 * np.asarray(Image.fromarray((spectral_noise(64, 256, 2.0, rng) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), np.float32) / 255.0
    a = a * np.clip(bristle * drift, 0, 1)
    endzone = np.clip(1 - np.minimum(x - start, end - x) / 260.0, 0, 1)
    holes = (rng.random((H, W)) < 0.25 * endzone ** 2).astype(np.float32)
    holes = cv2.GaussianBlur(holes, (0, 0), 1.2) > 0.2
    a[holes] *= 0.15
    a = cv2.GaussianBlur(a, (0, 0), 0.9)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(rgba).save(path)


def make_splatter(path, rng, S_=800):
    c = S_ / 2
    R = S_ * 0.30
    yy, xx = np.mgrid[0:S_, 0:S_].astype(np.float32)
    dx, dy = xx - c, yy - c
    r = np.sqrt(dx * dx + dy * dy)
    th = np.arctan2(dy, dx)
    ang = np.linspace(-np.pi, np.pi, 720)
    rn = noise1d(720, 18, rng, 4)
    rad = R * (1 + 0.07 * np.interp(th, ang, rn))
    img = Image.fromarray(((r < rad).astype(np.float32) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(rng.integers(10, 18)):  # spikes
        t = rng.uniform(-np.pi, np.pi)
        L = R * rng.uniform(1.15, 1.6)
        wdt = rng.uniform(0.02, 0.06)
        p0 = (c + np.cos(t - wdt) * R * 0.9, c + np.sin(t - wdt) * R * 0.9)
        p1 = (c + np.cos(t) * L, c + np.sin(t) * L)
        p2 = (c + np.cos(t + wdt) * R * 0.9, c + np.sin(t + wdt) * R * 0.9)
        d.polygon([p0, p1, p2], fill=255)
    for _ in range(rng.integers(25, 45)):  # droplets
        t = rng.uniform(-np.pi, np.pi)
        dist = R * rng.uniform(1.05, 1.55)
        rr = rng.uniform(2, 13) * (1.4 - (dist / R - 1))
        x0, y0 = c + np.cos(t) * dist, c + np.sin(t) * dist
        d.ellipse([x0 - rr, y0 - rr, x0 + rr, y0 + rr], fill=255)
    for _ in range(rng.integers(2, 4)):  # drips
        x0 = c + rng.uniform(-0.6, 0.6) * R
        y_start = c + np.sqrt(max(0.0, R * R - (x0 - c) ** 2)) * 0.95
        L = rng.uniform(0.2, 0.55) * R
        w0 = rng.uniform(6, 12)
        d.rounded_rectangle([x0 - w0, y_start - 10, x0 + w0, y_start + L], radius=w0, fill=255)
        d.ellipse([x0 - w0 * 1.3, y_start + L - w0 * 1.3, x0 + w0 * 1.3, y_start + L + w0 * 1.3], fill=255)
    a = cv2.GaussianBlur(np.asarray(img).astype(np.float32) / 255.0, (0, 0), 0.8)
    rgba = np.zeros((S_, S_, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype(np.uint8)
    Image.fromarray(rgba).save(path)


def texturas(p: Projeto, forcar: bool = False):
    p.fx.mkdir(parents=True, exist_ok=True)
    if not forcar and (p.fx / "splatter_4.png").exists():
        return
    from scipy.ndimage import gaussian_filter
    rng = np.random.default_rng(7)
    for k in range(2):  # fog (tileable, soft mist)
        n = spectral_noise(1024, 2048, 3.3, rng)
        n2 = spectral_noise(1024, 2048, 2.6, rng)
        f = np.clip((0.8 * n + 0.2 * n2 - 0.38) * 2.2, 0, 1) ** 1.6
        f = gaussian_filter(f, 6, mode="wrap")
        rgba = np.zeros((1024, 2048, 4), np.uint8)
        rgba[..., :3] = 255
        rgba[..., 3] = (np.clip(f, 0, 1) * 235).astype(np.uint8)
        Image.fromarray(rgba).save(p.fx / f"fog_{k}.png")
    for k in range(8):  # film grain frames (mid-gray, overlay blend)
        g = rng.normal(128, 38, (540, 960)).clip(0, 255).astype(np.uint8)
        Image.fromarray(g).save(p.fx / f"grain_{k}.png")
    base = spectral_noise(540, 960, 2.0, rng)  # grunge background
    fine = rng.normal(0, 1, (540, 960)).astype(np.float32)
    v = 7 + 10 * base + 1.2 * fine
    arr = np.asarray(Image.fromarray(np.clip(v, 0, 255).astype(np.uint8)).resize((1920, 1080), Image.BICUBIC)).astype(np.float32)
    sc = Image.new("L", (1920, 1080), 0)
    d = ImageDraw.Draw(sc)
    for _ in range(140):  # scratches
        x0, y0 = rng.uniform(0, 1920), rng.uniform(0, 1080)
        ang = rng.uniform(0, np.pi)
        L = rng.uniform(20, 160)
        d.line([x0, y0, x0 + np.cos(ang) * L, y0 + np.sin(ang) * L], fill=int(rng.uniform(8, 22)), width=1)
    arr = arr + np.asarray(sc, np.float32)
    rgb = np.stack([arr * 0.95, arr * 0.93, arr * 1.05], -1)
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(p.fx / "grunge.jpg", quality=90)
    for k in range(3):
        make_brush(p.fx / f"brush_{k}.png", rng)
    for k in range(5):
        make_splatter(p.fx / f"splatter_{k}.png", rng)
    print("texturas prontas")
