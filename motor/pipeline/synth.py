"""Instrument and SFX synthesis (numpy/scipy), 48 kHz stereo float32 arrays shaped (2, n)."""
import numpy as np
from scipy import signal

SR = 48000


def secs(t: float) -> int:
    return int(round(t * SR))


def midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


class Bus:
    """Stereo accumulation buffer with a tail margin."""

    def __init__(self, dur: float, tail: float = 8.0):
        self.x = np.zeros((2, secs(dur + tail)), np.float32)

    def add(self, t: float, st: np.ndarray, gain: float = 1.0):
        if st.ndim == 1:
            st = np.stack([st, st])
        i = secs(t)
        if i < 0:
            st = st[:, -i:]
            i = 0
        n = min(st.shape[1], self.x.shape[1] - i)
        if n > 0:
            self.x[:, i:i + n] += st[:, :n] * gain


def pan(mono: np.ndarray, p: float) -> np.ndarray:
    th = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.stack([mono * np.cos(th), mono * np.sin(th)]).astype(np.float32)


# ------------------------------------------------------------------ oscillators & filters
_TABLES: dict[int, np.ndarray] = {}


def saw_table(f0: float, n: int = 2048) -> np.ndarray:
    """Band-limited saw (harmonics up to ~12 kHz), Lanczos-sigma tapered to avoid ringing."""
    K = int(np.clip(min(12000.0, SR * 0.45) / max(f0, 1.0), 1, 400))
    if K not in _TABLES:
        ph = np.arange(n) / n
        k = np.arange(1, K + 1)
        amp = np.sinc(k / (K + 1)) / k
        tbl = (np.sin(2 * np.pi * np.outer(ph, k)) * amp).sum(axis=1)
        _TABLES[K] = (tbl / np.abs(tbl).max()).astype(np.float32)
    return _TABLES[K]


def osc(tbl: np.ndarray, freq, n: int, phase0: float = 0.0) -> np.ndarray:
    inc = (np.full(n, freq / SR) if np.isscalar(freq) else np.asarray(freq, np.float64) / SR)
    ph = (phase0 + np.cumsum(inc)) % 1.0
    idx = ph * len(tbl)
    i0 = idx.astype(np.int64)
    frac = (idx - i0).astype(np.float32)
    return tbl[i0 % len(tbl)] * (1 - frac) + tbl[(i0 + 1) % len(tbl)] * frac


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, min(fc, SR * 0.45), "low", fs=SR, output="sos"), x, axis=-1).astype(np.float32)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x, axis=-1).astype(np.float32)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"), x, axis=-1).astype(np.float32)


def biquad(kind, f0, gain_db=0.0, q=0.707):
    """RBJ cookbook biquad as a single sos row."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * np.pi * f0 / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    if kind == "peak":
        b = [1 + alpha * A, -2 * cw, 1 - alpha * A]
        a = [1 + alpha / A, -2 * cw, 1 - alpha / A]
    elif kind == "lowshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) - (A - 1) * cw + sa), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - sa)]
        a = [(A + 1) + (A - 1) * cw + sa, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - sa]
    elif kind == "highshelf":
        sa = 2 * np.sqrt(A) * alpha
        b = [A * ((A + 1) + (A - 1) * cw + sa), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - sa)]
        a = [(A + 1) - (A - 1) * cw + sa, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - sa]
    else:
        raise ValueError(kind)
    b, a = np.array(b) / a[0], np.array(a) / a[0]
    return np.concatenate([b, a])[None]


def eq(x, *bands):
    sos = np.concatenate([biquad(*b) for b in bands])
    return signal.sosfilt(sos, x, axis=-1).astype(np.float32)


def tv_filter(x: np.ndarray, fc_curve: np.ndarray, kind="low", q_oct=1.0, block=256, order=2):
    """Time-varying filter by blockwise coefficient updates (state carried)."""
    x2 = x if x.ndim == 2 else x[None]
    n = x2.shape[1]
    y = np.empty_like(x2)
    zi = None
    for b in range(0, n, block):
        fc = float(np.clip(fc_curve[min(b + block // 2, n - 1)], 25, SR * 0.44))
        if kind == "low":
            sos = signal.butter(order, fc, "low", fs=SR, output="sos")
        else:
            lo, hi = fc / 2 ** (q_oct / 2), min(fc * 2 ** (q_oct / 2), SR * 0.45)
            sos = signal.butter(order, [lo, hi], "band", fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], x2.shape[0], 2))
        seg, zi = signal.sosfilt(sos, x2[:, b:b + block], axis=1, zi=zi)
        y[:, b:b + block] = seg
    return (y if x.ndim == 2 else y[0]).astype(np.float32)


def env_ar(n: int, a: float, r: float, hold: float | None = None, curve: float = 1.6) -> np.ndarray:
    """Attack (a s), sustain until `hold` s, release (r s)."""
    t = np.arange(n) / SR
    hold = (n / SR - r) if hold is None else hold
    att = np.clip(t / max(a, 1e-4), 0, 1) ** curve
    rel = np.clip(1 - (t - hold) / max(r, 1e-4), 0, 1) ** curve
    return (att * rel).astype(np.float32)


def noise(n, rng, color="white"):
    w = rng.standard_normal(n).astype(np.float32)
    if color == "white":
        return w
    if color == "pink":  # Paul Kellet economy pink
        b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
        a = [1, -2.494956002, 2.017265875, -0.522189400]
        p = signal.lfilter(b, a, w).astype(np.float32)
        return p / (np.abs(p).max() + 1e-9)
    if color == "brown":
        br = signal.lfilter([1.0], [1.0, -0.997], w).astype(np.float32)
        br -= signal.lfilter([0.002], [1, -0.998], br).astype(np.float32)
        return br / (np.abs(br).max() + 1e-9)
    raise ValueError(color)


def smooth_random(n, rng, points_per_sec=0.5, lo=0.0, hi=1.0):
    k = max(4, int(n / SR * points_per_sec) + 3)
    pts = rng.uniform(lo, hi, k)
    xs = np.linspace(0, n - 1, k)
    from scipy.interpolate import CubicSpline
    return np.clip(CubicSpline(xs, pts)(np.arange(n)), lo, hi).astype(np.float32)


# ------------------------------------------------------------------ reverb
def make_ir(dur=3.2, rt60=2.6, dark_fc=2600, seed=11, pre=0.018, width=1.0):
    rng = np.random.default_rng(seed)
    n = secs(dur)
    t = np.arange(n) / SR
    env = 10 ** (-3 * t / rt60)
    irs = []
    for ch in range(2):
        w = rng.standard_normal(n).astype(np.float32)
        bright = w * env
        dark = lp(w, dark_fc) * env
        mix = np.exp(-t / 0.35)
        ir = bright * mix + dark * (1 - mix) * 1.6
        # sparse early reflections
        for _ in range(9):
            k = secs(rng.uniform(0.004, 0.07))
            ir[k] += rng.uniform(-0.6, 0.6)
        irs.append(np.concatenate([np.zeros(secs(pre), np.float32), ir]))
    ir = np.stack(irs)
    mid = ir.mean(0, keepdims=True)
    ir = mid + (ir - mid) * width
    return (ir / np.sqrt((ir ** 2).sum(axis=1, keepdims=True).mean())).astype(np.float32)


def reverb(x: np.ndarray, ir: np.ndarray, wet: float) -> np.ndarray:
    """Stereo convolution reverb; x (2, n). Returns wet signal only (same length + tail cut)."""
    n = x.shape[1]
    out = np.stack([
        signal.oaconvolve(x[0], ir[0])[:n] * 0.7 + signal.oaconvolve(x[1], ir[0])[:n] * 0.3,
        signal.oaconvolve(x[1], ir[1])[:n] * 0.7 + signal.oaconvolve(x[0], ir[1])[:n] * 0.3,
    ]).astype(np.float32)
    return out * wet


# ------------------------------------------------------------------ instruments
def strings_note(midi, dur, rng, voices=6, detune_cents=13.0, cutoff=1500.0, a=1.6, r=2.2, vib=0.0032, gain=1.0):
    """Dark supersaw ensemble note (dur = held time; release tail appended)."""
    n = secs(dur + r)
    f = midi_hz(midi)
    t = np.arange(n) / SR
    tbl = saw_table(f * 1.03)
    out = np.zeros((2, n), np.float32)
    for v in range(voices):
        pos = (v / (voices - 1) - 0.5) if voices > 1 else 0.0
        fv = f * 2 ** (pos * 2 * detune_cents / 1200)
        vdepth = vib * np.clip((t - 0.5) / 1.2, 0, 1)
        freq = fv * (1 + vdepth * np.sin(2 * np.pi * rng.uniform(4.3, 5.4) * t + rng.uniform(0, 6.28)))
        out += pan(osc(tbl, freq, n, rng.uniform()), pos * 1.3)
    out = lp(out, cutoff, order=2)
    out = lp(out, cutoff * 2.6, order=2)
    out *= env_ar(n, a, r, hold=dur) * (gain / voices ** 0.5)
    return out


def pad_chord(notes, dur, rng, gain=1.0, **kw):
    out = None
    for m in notes:
        x = strings_note(m, dur, rng, gain=gain * (0.85 if m > 60 else 1.0), **kw)
        out = x if out is None else out + x
    return out


def choir_note(midi, dur, rng, voices=5, a=1.8, r=2.2, gain=1.0, vowel="a"):
    """Formant-filtered saw ensemble ('aah')."""
    n = secs(dur + r)
    f = midi_hz(midi)
    t = np.arange(n) / SR
    tbl = saw_table(f)
    src = np.zeros(n, np.float32)
    for v in range(voices):
        fv = f * 2 ** (rng.uniform(-9, 9) / 1200)
        freq = fv * (1 + 0.005 * np.sin(2 * np.pi * rng.uniform(5.0, 6.0) * t + rng.uniform(0, 6.28)))
        src += osc(tbl, freq, n, rng.uniform())
    src += 0.08 * noise(n, rng)  # breath
    forms = {"a": [(700, 110, 1.0), (1150, 130, 0.55), (2700, 190, 0.22)],
             "o": [(450, 90, 1.0), (800, 110, 0.45), (2830, 190, 0.12)]}[vowel]
    y = np.zeros(n, np.float32)
    for fc, bw, g in forms:
        y += g * bp(src, fc - bw, fc + bw, order=2)
    y = lp(y, 3500)
    st = np.stack([y, np.roll(y, secs(0.011))])
    return (st * env_ar(n, a, r, hold=dur) * gain / voices ** 0.5 * 2.2).astype(np.float32)


def musicbox_note(midi, rng, vel=1.0, dur=3.2):
    n = secs(dur)
    t = np.arange(n) / SR
    f = midi_hz(midi)
    parts = [(1, 1.0, 2.3), (2, 0.40, 1.4), (3, 0.13, 0.9), (4.16, 0.22, 0.55), (5.43, 0.09, 0.36), (6.79, 0.05, 0.25)]
    y = np.zeros(n, np.float32)
    for r_, a_, d_ in parts:
        if f * r_ < SR * 0.45:
            y += a_ * np.exp(-t / d_) * np.sin(2 * np.pi * f * r_ * t * (1 + rng.uniform(-3e-4, 3e-4)) + rng.uniform(0, 6.28))
    y *= np.clip(t / 0.0025, 0, 1)
    click = hp(noise(n, rng), 3000) * np.exp(-t / 0.004) * 0.12
    return ((y + click) * vel * 0.5).astype(np.float32)


def piano_low(midi, rng, dur=6.0, vel=1.0):
    """Dark felt-piano-like low note (additive with slight inharmonicity)."""
    n = secs(dur)
    t = np.arange(n) / SR
    f = midi_hz(midi)
    B = 0.0004
    y = np.zeros(n, np.float32)
    for k in range(1, 14):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > 6000:
            break
        y += (1 / k ** 1.3) * np.exp(-t * (0.35 + 0.22 * k)) * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28))
    y *= np.clip(t / 0.004, 0, 1)
    y = lp(y, 1800)
    return (y * vel * 0.6).astype(np.float32)


def bell(rng, f0=146.83, dur=10.0, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    parts = [(0.5, 0.55, 7.5), (1.0, 0.75, 5.2), (1.183, 0.45, 4.0), (1.506, 0.32, 3.1), (2.0, 0.55, 2.7),
             (2.514, 0.22, 1.9), (2.662, 0.18, 1.7), (3.011, 0.16, 1.3), (4.166, 0.10, 0.9), (5.433, 0.07, 0.6)]
    y = np.zeros(n, np.float32)
    for r_, a_, d_ in parts:
        for beat in (-0.35, 0.35):
            y += 0.5 * a_ * np.exp(-t / d_) * np.sin(2 * np.pi * (f0 * r_ + beat) * t + rng.uniform(0, 6.28))
    y *= np.clip(t / 0.002, 0, 1)
    strike = bp(noise(n, rng), 900, 4500) * np.exp(-t / 0.012) * 0.5
    return ((y + strike) * vel * 0.45).astype(np.float32)


def boom(rng, dur=4.0, f0=78, f1=31, glide=0.35, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / glide)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 1.1) * np.clip(t / 0.004, 0, 1)
    thump = lp(noise(n, rng), 700) * np.exp(-t / 0.06) * 0.9
    y = np.tanh(1.6 * (body + thump)) * vel
    return y.astype(np.float32)


def hit(rng, vel=1.0):
    n = secs(2.5)
    t = np.arange(n) / SR
    low = boom(rng, dur=2.5, f0=95, f1=45, glide=0.12) * 0.7
    metal = np.zeros(n, np.float32)
    for fr, d_ in [(180, 0.5), (412, 0.35), (611, 0.3), (1130, 0.2), (1790, 0.12)]:
        metal += np.exp(-t / d_) * np.sin(2 * np.pi * fr * t + rng.uniform(0, 6.28))
    crack = bp(noise(n, rng), 1200, 6000) * np.exp(-t / 0.02)
    return ((low + 0.12 * metal + 0.35 * crack) * vel).astype(np.float32)


def braam(rng, dur=5.0, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    x = np.zeros((2, n), np.float32)
    for m, g in [(26, 1.0), (38, 0.9), (45, 0.6), (50, 0.5), (53, 0.35)]:
        x += strings_note(m, dur - 0.3, rng, voices=5, detune_cents=18, cutoff=9000, a=0.03, r=0.3, vib=0.0, gain=g)[:, :n]
    fc = 140 + 3200 * (1 - np.exp(-t / 0.10)) * np.exp(-t / 0.9) + 220 * np.exp(-t / 3)
    x = tv_filter(x, fc, "low", block=256, order=2)
    x = np.tanh(3.0 * x) * np.exp(-t / 2.4)
    sub = boom(rng, dur=dur, f0=60, f1=28, glide=0.6) * 0.8
    return ((x + sub) * vel * 0.8).astype(np.float32)


def taiko(rng, vel=1.0, f=68.0):
    n = secs(1.4)
    t = np.arange(n) / SR
    fr = f * (1 + 0.6 * np.exp(-t / 0.025))
    body = np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / 0.32)
    skin = bp(noise(n, rng), 140, 900) * np.exp(-t / 0.035) * 0.8
    y = np.tanh(1.3 * (body + skin)) * np.clip(t / 0.002, 0, 1)
    return (y * vel).astype(np.float32)


def rim(rng, vel=1.0):
    n = secs(0.25)
    t = np.arange(n) / SR
    y = bp(noise(n, rng), 1500, 5000) * np.exp(-t / 0.012) + 0.4 * np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.02)
    return (y * vel * 0.5).astype(np.float32)


def heartbeat(rng, vel=1.0):
    n = secs(1.2)
    y = np.zeros(n, np.float32)
    for off, g in [(0.0, 1.0), (0.27, 0.72)]:
        k = secs(off)
        m = n - k
        t = np.arange(m) / SR
        th = np.sin(2 * np.pi * 52 * t) * np.exp(-t / 0.11) * np.clip(t / 0.008, 0, 1)
        th += lp(noise(m, rng), 180) * np.exp(-t / 0.04) * 0.8
        y[k:] += th * g
    return (lp(y, 170) * vel * 1.6).astype(np.float32)


def whoosh(rng, dur=0.9, f0=250, fpk=3500, f1=600, vel=1.0, p0=-0.7, p1=0.7):
    n = secs(dur)
    t = np.arange(n) / SR
    u = t / dur
    fc = np.where(u < 0.6, f0 * (fpk / f0) ** (u / 0.6), fpk * (f1 / fpk) ** ((u - 0.6) / 0.4))
    x = noise(n, rng)
    y = tv_filter(x, fc, "band", q_oct=1.2, block=128)
    amp = np.sin(np.pi * np.clip(u, 0, 1)) ** 2.2
    y = y * amp * vel * 1.4
    pp = p0 + (p1 - p0) * u
    th = (pp + 1) * np.pi / 4
    return np.stack([y * np.cos(th), y * np.sin(th)]).astype(np.float32)


def riser(rng, dur=3.0, vel=1.0):
    """Ends at its peak (align the END to the target time)."""
    n = secs(dur)
    t = np.arange(n) / SR
    u = t / dur
    fc = 180 * (9000 / 180) ** u
    y = tv_filter(noise(n, rng), fc, "band", q_oct=1.0, block=128) * u ** 2.4
    tone = np.sin(2 * np.pi * np.cumsum(90 * (8 ** u)) / SR) * u ** 3 * 0.15
    st = np.stack([y + tone, np.roll(y, 37) + tone])
    return (st * vel).astype(np.float32)


def swell(rng, notes, dur=2.4, vel=1.0):
    """Reverse-swell into a chord: crescendo that peaks at the end."""
    x = pad_chord(notes, dur, rng, a=dur, r=0.05, cutoff=2600, gain=1.0)
    n = secs(dur)
    x = x[:, :n]
    u = np.arange(n) / n
    ch = choir_note(notes[1] + 12, dur, rng, a=dur, r=0.05)[:, :n]
    y = (x + 0.6 * ch) * (u ** 2.0)[None]
    y += riser(rng, dur, 0.25)[:, :n]
    return (y * vel).astype(np.float32)


def splat(rng, vel=1.0):
    n = secs(0.6)
    y = np.zeros(n, np.float32)
    for i in range(rng.integers(3, 6)):
        k = secs(rng.uniform(0, 0.12)) if i else 0
        m = secs(rng.uniform(0.01, 0.03))
        b = lp(noise(m, rng), rng.uniform(1500, 3500)) * np.exp(-np.arange(m) / SR / 0.008)
        y[k:k + m] += b[: n - k] * (1.0 if i == 0 else rng.uniform(0.3, 0.7))
    t = np.arange(n) / SR
    y += bp(noise(n, rng), 280, 1100) * np.exp(-t / 0.09) * 0.7
    return (y * vel).astype(np.float32)


def brush(rng, dur=0.45, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    fc = 1400 * (5200 / 1400) ** (t / dur)
    y = tv_filter(noise(n, rng), fc, "band", q_oct=1.6, block=128)
    amp = np.clip(t / 0.07, 0, 1) * np.exp(-np.clip(t - 0.07, 0, None) / 0.14)
    return pan(y * amp * vel * 0.9, rng.uniform(-0.3, 0.3))


def tick(rng, vel=1.0):
    n = secs(0.2)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * 1850 * t) * np.exp(-t / 0.03) + hp(noise(n, rng), 4000) * np.exp(-t / 0.004)
    return (y * 0.35 * vel).astype(np.float32)


def rumble(rng, dur=4.5, vel=1.0):
    n = secs(dur)
    t = np.arange(n) / SR
    y = lp(noise(n, rng, "brown"), 95, order=4)
    y *= 1 + 0.35 * np.sin(2 * np.pi * 5.5 * t)
    y += 0.5 * np.sin(2 * np.pi * 36.7 * t)
    y *= env_ar(n, 0.9, 2.0)
    y = y / (np.abs(y).max() + 1e-9)
    return np.stack([y, np.roll(y, 61)]).astype(np.float32) * vel


def sword(rng, vel=1.0):
    n = secs(2.2)
    t = np.arange(n) / SR
    scrape = tv_filter(noise(n, rng), 2200 * (9000 / 2200) ** np.clip(t / 0.28, 0, 1), "band", q_oct=0.8, block=64)
    scrape *= np.clip(t / 0.03, 0, 1) * np.exp(-np.clip(t - 0.2, 0, None) / 0.05)
    ring = np.zeros(n, np.float32)
    for fr, d_ in [(1870, 1.4), (2980, 1.1), (4120, 0.9), (5330, 0.7), (7210, 0.5)]:
        ring += np.exp(-np.clip(t - 0.18, 0, None) / d_) * np.sin(2 * np.pi * fr * (1 + 0.0015 * np.sin(2 * np.pi * 6 * t)) * t) * (t > 0.16)
    y = 0.7 * scrape + 0.16 * ring
    return pan(y * vel, 0.25)


def shimmer(rng, dur=4.0, vel=1.0, notes=(86, 93, 98, 101)):
    n = secs(dur)
    t = np.arange(n) / SR
    out = np.zeros((2, n), np.float32)
    for m in notes:
        f = midi_hz(m)
        y = np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * (0.6 + 0.4 * np.sin(2 * np.pi * rng.uniform(5, 9) * t))
        out += pan(y.astype(np.float32), rng.uniform(-0.8, 0.8))
    out *= env_ar(n, dur * 0.4, dur * 0.5) * 0.12 * vel
    return out


def slash(rng, vel=1.0):
    y = whoosh(rng, 0.38, 600, 7000, 2500, vel=1.2, p0=-0.8, p1=0.8)
    s = sword(rng, 0.5)[:, : y.shape[1] + secs(0.6)]
    out = np.zeros((2, max(y.shape[1], s.shape[1])), np.float32)
    out[:, : y.shape[1]] += y
    out[:, : s.shape[1]] += s * 0.6
    return out * vel


def drips(rng, vel=1.0):
    n = secs(1.6)
    out = np.zeros(n, np.float32)
    for k in range(3):
        o = secs(0.12 + k * rng.uniform(0.28, 0.4))
        m = secs(0.09)
        t = np.arange(m) / SR
        f = 1100 * np.exp(-t / 0.03) + 280
        d = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035)
        out[o:o + m] += d[: n - o] * (0.8 - 0.15 * k)
    return pan(out * vel * 0.6, 0.0)


def fire(rng, dur, vel=1.0):
    n = secs(dur)
    roar = lp(noise(n, rng, "brown"), 380) * 0.5
    cr = np.zeros(n, np.float32)
    k = 0
    while True:
        k += int(rng.exponential(SR / 11))
        if k >= n - 400:
            break
        m = int(rng.uniform(40, 300))
        cr[k:k + m] += rng.standard_normal(m).astype(np.float32) * rng.uniform(0.05, 1.0) ** 2 * np.exp(-np.arange(m) / (m / 3))
    cr = bp(cr, 1500, 7000)
    y = roar + 0.9 * cr
    return np.stack([y, np.roll(y, 211)]).astype(np.float32) * vel


def wind(rng, dur, vel=1.0):
    n = secs(dur)
    out = []
    for ch in range(2):
        x = noise(n, rng, "pink")
        fc = 260 + 520 * smooth_random(n, rng, 0.35)
        y = tv_filter(x, fc, "band", q_oct=1.6, block=512)
        g = 0.55 + 0.45 * smooth_random(n, rng, 0.25)
        out.append(y * g)
    return np.stack(out).astype(np.float32) * vel * 2.2


def drone(rng, dur, root=38, vel=1.0, a=3.0, r=3.0):
    n = secs(dur)
    t = np.arange(n) / SR
    f = midi_hz(root - 12)
    y = np.sin(2 * np.pi * f * t) * 0.9 + 0.45 * np.sin(2 * np.pi * f * 2 * t + 0.4)
    tri = osc(saw_table(f * 2), f * 2, n) * 0.12
    y = lp(y + tri, 160) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.07 * t))
    y *= env_ar(n, a, r)
    return np.stack([y, y]).astype(np.float32) * vel
