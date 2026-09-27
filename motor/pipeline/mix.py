"""Voice processing (per-voice `fx` preset), ducking and mastering.

Outputs .estudio/public/audio/mix-<fmt>.wav (24-bit) and, for the first format, saida/narracao.wav
and saida/trilha-sonora.wav (each normalized to -16 LUFS on its own, for reuse). Prints the
loudness/peak report and the voice-over-bed margin, and saves a spectrogram PNG.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pyloudnorm as pyln
from scipy import ndimage, signal
from scipy.io import wavfile

import synth as s
from ambiente import ffmpeg
from projeto import Projeto
from synth import SR, secs

METER = pyln.Meter(SR)
CEIL_DB = -1.5


# ------------------------------------------------------------------ dynamics
def gain_smooth(target_db, att_ms, rel_ms, frame):
    """One-pole attack/release smoothing of a gain-reduction curve (dB, >=0 means reduction)."""
    a_att = np.exp(-frame / (SR * att_ms / 1000))
    a_rel = np.exp(-frame / (SR * rel_ms / 1000))
    out = np.empty_like(target_db)
    g = 0.0
    for i, v in enumerate(target_db):
        a = a_att if v > g else a_rel
        g = a * g + (1 - a) * v
        out[i] = g
    return out


def compress(x, thr_db=-22.0, ratio=3.0, att_ms=8, rel_ms=140, knee_db=6.0):
    frame = 48
    mono = x if x.ndim == 1 else x.mean(0)
    n = len(mono) // frame * frame
    rms = np.sqrt(np.mean(mono[:n].reshape(-1, frame) ** 2, axis=1) + 1e-12)
    over = 20 * np.log10(rms) - thr_db
    gr = np.where(over <= -knee_db / 2, 0.0,
                  np.where(over >= knee_db / 2, over * (1 - 1 / ratio),
                           (1 - 1 / ratio) * (over + knee_db / 2) ** 2 / (2 * knee_db)))
    gr = gain_smooth(gr, att_ms, rel_ms, frame)
    g = 10 ** (-np.interp(np.arange(len(mono)), np.arange(len(gr)) * frame + frame / 2, gr) / 20)
    return (x * g).astype(np.float32)


def limiter(x, ceil_db=CEIL_DB, look_ms=5.0, rel_ms=90.0):
    ceil = 10 ** (ceil_db / 20)
    pk = np.abs(x).max(0) if x.ndim == 2 else np.abs(x)
    req = np.minimum(1.0, ceil / (pk + 1e-12))
    L = max(2, secs(look_ms / 1000))
    g = ndimage.minimum_filter1d(req, size=L, origin=-(L // 2))
    g = ndimage.uniform_filter1d(g, size=L, origin=(L - 1) // 2)  # causal-ish ramp into the peak
    frame = 32  # release smoothing on a decimated grid
    gr_db = -20 * np.log10(np.maximum(g[: len(g) // frame * frame].reshape(-1, frame).min(1), 1e-6))
    gr_db = gain_smooth(gr_db, 0.01, rel_ms, frame)
    gs = np.minimum(10 ** (-np.interp(np.arange(len(g)), np.arange(len(gr_db)) * frame, gr_db) / 20), g)
    return np.clip(x * gs, -ceil, ceil).astype(np.float32)


def lufs(x):
    data = x.T if x.ndim == 2 else x
    return METER.integrated_loudness(data.astype(np.float64))


def set_lufs(x, target):
    return (x * 10 ** ((target - lufs(x)) / 20)).astype(np.float32)


# ------------------------------------------------------------------ voices
def whisper_layer(x, rng):
    nper, nov = 1024, 768
    _, _, X = signal.stft(x, SR, nperseg=nper, noverlap=nov)
    env = ndimage.uniform_filter1d(np.abs(X), size=11, axis=0)
    _, _, N = signal.stft(rng.standard_normal(len(x)), SR, nperseg=nper, noverlap=nov)
    N = N / (np.abs(N) + 1e-9)
    _, y = signal.istft(env * N, SR, nperseg=nper, noverlap=nov)
    y = s.hp(y[: len(x)].astype(np.float32), 700)
    return y * (np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(y ** 2)) + 1e-9))


IRS = {}


def ir(name):
    if name not in IRS:
        IRS[name] = {"narr": lambda: s.make_ir(1.4, 1.0, 5000, seed=21, pre=0.012),
                     "villain": lambda: s.make_ir(4.0, 3.2, 1700, seed=22, pre=0.03, width=1.3),
                     "hero": lambda: s.make_ir(1.2, 0.8, 4500, seed=23, pre=0.008)}[name]()
    return IRS[name]


def deess(x, thr_db=-30.0, ratio=3.0, corte=6000):
    """Tames sibilance: gain reduction driven by the 6 kHz+ band only."""
    sib = s.hp(x, corte)
    frame = 64
    n = len(sib) // frame * frame
    rms = np.sqrt(np.mean(sib[:n].reshape(-1, frame) ** 2, axis=1) + 1e-12)
    over = np.maximum(0.0, 20 * np.log10(rms + 1e-12) - thr_db) * (1 - 1 / ratio)
    over = gain_smooth(over, 1.0, 60.0, frame)
    g = 10 ** (-np.interp(np.arange(len(x)), np.arange(len(over)) * frame + frame / 2, over) / 20)
    return (x - sib * (1 - g)).astype(np.float32)


def voice_chain(x, fx, rng):
    """fx: narrador (warm, short room) · sombrio (whisper layer, long dark reverb) · sala (bright, small
    room) · seco (like narrador, no reverb) · gravacao (recorded speech: rumble out, de-essed, no reverb)."""
    if fx == "gravacao":
        x = s.hp(x, 90, order=4)
        x = s.eq(x, ("lowshelf", 130, 1.0), ("peak", 260, -2.0, 1.2), ("peak", 3000, 2.0, 0.9),
                 ("highshelf", 9500, -1.0))
        x = deess(x)
        x = compress(x, -26, 3.2, 8, 130)
        dry = np.stack([x, x])
        return np.concatenate([dry, np.zeros((2, secs(0.5)), np.float32)], axis=1), x
    x = s.hp(x, 105 if fx == "sala" else 75)
    if fx == "sala":
        x = s.eq(x, ("lowshelf", 180, 1.0), ("peak", 3400, 3.0, 1.0), ("highshelf", 9000, -1.0))
    else:
        x = s.eq(x, ("lowshelf", 150, 3.0), ("peak", 320, -1.5, 1.2), ("peak", 3200, 2.0, 1.0), ("highshelf", 9500, -1.5))
    x = compress(x, -24, 3.0, 6, 120)
    if fx == "sombrio":
        w = whisper_layer(x, rng)
        x = np.tanh(1.4 * x) / 1.4 * 0.85 + 0.42 * w
        x = s.eq(x, ("lowshelf", 120, 2.0), ("highshelf", 7000, -2.0))
    dry = np.stack([x, x])
    dry_p = np.concatenate([dry, np.zeros((2, secs(4.5)), np.float32)], axis=1)
    if fx == "seco":
        return dry_p, x
    kind, wet = {"narrador": ("narr", 0.10), "sombrio": ("villain", 0.34), "sala": ("hero", 0.12)}[fx]
    wet_sig = s.reverb(dry_p, ir(kind), wet)
    if fx == "sombrio":
        wet_sig = s.lp(wet_sig, 3500)
    return dry_p + wet_sig, x


# ------------------------------------------------------------------ mixing
def spectrogram_png(x, tl, path):
    from PIL import Image, ImageDraw
    mono = x.mean(0)
    f, _, Z = signal.stft(mono, SR, nperseg=4096, noverlap=4096 - 2400)
    mag = 20 * np.log10(np.abs(Z) + 1e-7)
    rows = 360  # log-frequency rows 30 Hz..16 kHz
    idx = np.searchsorted(f, np.geomspace(30, 16000, rows)).clip(0, len(f) - 1)
    img = np.clip((mag[idx][::-1] + 90) / 80, 0, 1)
    im = Image.fromarray((img * 255).astype(np.uint8)).resize((1800, rows)).convert("RGB")
    d = ImageDraw.Draw(im)
    dur = x.shape[1] / SR
    for sc in tl["scenes"]:
        xx = sc["t0"] / dur * 1800
        d.line([(xx, 0), (xx, rows)], fill=(255, 80, 80))
        d.text((xx + 3, 3), sc["id"], fill=(255, 255, 0))
    env = np.sqrt(ndimage.uniform_filter1d(mono ** 2, secs(0.4)) + 1e-12)  # loudness strip
    envdb = 20 * np.log10(env)
    strip = Image.new("RGB", (1800, 120), (20, 20, 20))
    ds = ImageDraw.Draw(strip)
    ds.line([(i, 120 - np.clip((envdb[int(i / 1800 * (len(envdb) - 1))] + 60) / 60, 0, 1) * 118) for i in range(1800)], fill=(120, 220, 255))
    for db in (-12, -24, -36, -48):
        yy = 120 - (db + 60) / 60 * 118
        ds.line([(0, yy), (1800, yy)], fill=(70, 70, 70))
        ds.text((2, yy - 11), f"{db}", fill=(150, 150, 150))
    out = Image.new("RGB", (1800, rows + 120))
    out.paste(im, (0, 0))
    out.paste(strip, (0, rows))
    out.save(path)


def write_pcm24(p: Projeto, x, path):
    tmp = p.work / f"_tmp_{path.stem}.wav"
    wavfile.write(tmp, SR, x.T.astype(np.float32))
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-i", str(tmp), "-c:a", "pcm_s24le", str(path))
    tmp.unlink()


def true_peak_and_lufs(path):
    err = ffmpeg("-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-", quiet=False)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def voz_das_falas(p: Projeto, fmt: str, tl: dict, n: int, rng):
    """Images mode: one processed TTS line at a time, placed at its timeline position."""
    voices = p.roteiro(fmt)["voices"]
    voice = np.zeros((2, n + secs(5)), np.float32)
    dry_mono = np.zeros(n + secs(5), np.float32)
    for sc in tl["scenes"]:
        for ln in sc["lines"]:
            _, x = wavfile.read(p.work / f"lines_{fmt}" / f"{ln['id']}.wav")
            st, dry = voice_chain(x.astype(np.float32), voices[ln["speaker"]].get("fx", "narrador"), rng)
            i = secs(ln["t"])
            m = min(st.shape[1], voice.shape[1] - i)
            voice[:, i:i + m] += st[:, :m]
            dry_mono[i:i + len(dry)] += dry[: len(dry_mono) - i]
    return voice, dry_mono


def voz_gravada(p: Projeto, fmt: str, n: int, rng):
    """Video mode: the edited source audio, processed as one continuous take."""
    src = p.work / f"voz-{fmt}.wav"
    if not src.exists():
        raise FileNotFoundError(f"{src} não existe — rode `estudio.py montar`")
    _, x = wavfile.read(src)
    x = x.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    st, dry = voice_chain(x, (p.cfg.get("voice") or {}).get("fx", "gravacao"), rng)
    voice = np.zeros((2, n + secs(5)), np.float32)
    dry_mono = np.zeros(n + secs(5), np.float32)
    m = min(st.shape[1], voice.shape[1])
    voice[:, :m] += st[:, :m]
    dry_mono[: min(len(dry), len(dry_mono))] += dry[: len(dry_mono)]
    return voice, dry_mono


def mixar(p: Projeto, fmt: str, stems_saida: bool):
    cfg = p.cfg["mix"]
    music_lufs = cfg["music_lufs"][fmt] if isinstance(cfg["music_lufs"], dict) else cfg["music_lufs"]
    tl = json.loads(p.timeline_path(fmt).read_text())
    rng = np.random.default_rng(5)
    n = secs(tl["duration"])
    stems = {}
    for name in ("music", "amb", "sfx"):
        _, x = wavfile.read(p.work / f"stems_{fmt}" / f"{name}.wav")
        x = x.T.astype(np.float32)
        stems[name] = np.pad(x, ((0, 0), (0, max(0, n - x.shape[1]))))[:, :n]

    voice, dry_mono = (voz_gravada(p, fmt, n, rng) if p.modo == "video"
                       else voz_das_falas(p, fmt, tl, n, rng))
    voice, dry_mono = voice[:, :n], dry_mono[:n]

    voice = set_lufs(voice, cfg["voice_lufs"])  # loudness staging
    dry_mono *= 10 ** ((cfg["voice_lufs"] - lufs(np.stack([dry_mono, dry_mono]))) / 20)
    music = set_lufs(stems["music"], music_lufs)
    amb = set_lufs(stems["amb"], -31.0) if np.abs(stems["amb"]).max() > 0 else stems["amb"]
    sfx = set_lufs(stems["sfx"], -23.0) if np.abs(stems["sfx"]).max() > 0 else stems["sfx"]

    frame = 240  # voice activity -> ducking gain (look-ahead 90 ms)
    nn = len(dry_mono) // frame * frame
    rms = np.sqrt(np.mean(dry_mono[:nn].reshape(-1, frame) ** 2, axis=1) + 1e-12)
    act = np.clip((20 * np.log10(rms) + 50) / 14, 0, 1)
    act = ndimage.maximum_filter1d(act, size=int(0.25 * SR / frame))  # bridge tiny gaps between words
    act = np.roll(act, -int(0.09 * SR / frame))
    duck_db = gain_smooth(act * cfg["ducking_db"], 60, 520, frame)
    duck = 10 ** (-np.interp(np.arange(n), np.arange(len(duck_db)) * frame, duck_db) / 20)
    duck_sfx = 10 ** (-np.interp(np.arange(n), np.arange(len(duck_db)) * frame, duck_db * 0.33) / 20)

    bed = (music + amb) * duck[None]
    mix = voice + bed + sfx * duck_sfx[None]
    mix = compress(mix, -16, 2.0, 25, 260, 8.0)
    for _ in range(3):
        mix = limiter(set_lufs(mix, cfg["lufs"]), CEIL_DB)
    fade = secs(0.02)
    mix[:, :fade] *= np.linspace(0, 1, fade)

    out = p.audio / f"mix-{fmt}.wav"
    write_pcm24(p, mix, out)
    i_lufs, tp = true_peak_and_lufs(out)
    sp = np.zeros(n, bool)  # speech mask, padded: act only covers whole frames
    fala = np.repeat(act > 0.8, frame)[:n]
    sp[: len(fala)] = fala
    db = lambda x: 10 * np.log10(np.mean(x ** 2) + 1e-12)  # noqa: E731
    margin = db(voice[:, sp]) - db(bed[:, sp])
    print(f"[{fmt}] integrado {i_lufs} LUFS, pico real {tp} dBTP, voz acima da trilha durante as falas: {margin:.1f} dB")
    spectrogram_png(mix, tl, p.work / f"espectrograma_{fmt}.png")
    if stems_saida:
        write_pcm24(p, limiter(set_lufs(voice, -16.0), -1.5), p.saida / "narracao.wav")
        track = music + amb + sfx
        for _ in range(3):
            track = limiter(set_lufs(track, -16.0), -1.5)
        write_pcm24(p, track, p.saida / "trilha-sonora.wav")
        print("stems: saida/narracao.wav, saida/trilha-sonora.wav")
    return {"lufs": i_lufs, "true_peak": tp, "margem_voz_db": round(float(margin), 1)}


def gerar(p: Projeto, fmts=None):
    fmts = fmts or p.formatos()
    first = "main" if "main" in p.formatos() else p.formatos()[0]
    return {fmt: mixar(p, fmt, stems_saida=(fmt == first)) for fmt in fmts}
