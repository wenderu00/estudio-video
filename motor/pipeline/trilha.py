"""Original score + SFX composed to the timeline.

Each scene picks a mood preset (`music`); presets anchor chords, themes and hits to the roles of
the scene's lines (title, bullets, statement, quote…) and to its SFX cues. Harmony is written in
D minor and transposed to projeto.json `music.key`. Writes .estudio/work/stems_<fmt>/{music,amb,sfx}.wav.
"""
from __future__ import annotations

import json

import numpy as np
from scipy.io import wavfile

import synth as s
from projeto import Projeto, norm
from synth import SR, Bus, pan

CH = {
    "Dm": [50, 53, 57, 62], "Dm9": [50, 57, 64, 65], "Bb": [46, 53, 58, 62], "Bbmaj7": [46, 50, 53, 57],
    "Gm": [43, 50, 55, 58], "A": [45, 52, 57, 61], "Asus4": [45, 52, 57, 62], "A7": [45, 52, 55, 61],
    "F": [41, 48, 53, 57], "C": [48, 52, 55, 60], "Ebmaj7": [51, 55, 58, 62], "C#dim7": [49, 52, 55, 58],
}
BASS = {"Dm": 38, "Dm9": 38, "Bb": 34, "Bbmaj7": 34, "Gm": 31, "A": 33, "Asus4": 33, "A7": 33, "F": 29,
        "C": 36, "Ebmaj7": 39, "C#dim7": 37}
CHOIR = {"Dm": [62, 65, 69], "Dm9": [62, 65, 69], "Bb": [62, 65, 70], "Bbmaj7": [62, 65, 69], "Gm": [62, 67, 70],
         "A": [64, 69, 73], "Asus4": [64, 69, 74], "C#dim7": [64, 67, 70], "Ebmaj7": [63, 67, 70], "C": [64, 67, 72],
         "F": [60, 65, 69], "A7": [64, 67, 73]}
# default leitmotif (music box), 3/4, 8 bars: (beat, midi, length in beats)
THEME = [(0, 69, 1), (1, 74, 1), (2, 76, 1), (3, 77, 2), (5, 76, 1), (6, 74, 1), (7, 73, 1), (8, 74, 1), (9, 69, 3),
         (12, 70, 1), (13, 74, 1), (14, 79, 1), (15, 77, 2), (17, 76, 1), (18, 74, 1), (19, 76, 1), (20, 73, 1), (21, 74, 3)]
THEME_BASS = [50, 46, 45, 50, 46, 43, 45, 50]
THEME_HARM = ["Dm", "Bb", "A", "Dm", "Bb", "Gm", "A", "Dm"]
# I–V–vi–IV em Fá maior: o leito claro dos climas de relato pessoal (leve/brisa/pulso).
# Os climas herdados do modo imagens são todos em ré menor, com cordas graves e violoncelo —
# vocabulário de narrativa dramática, pesado demais para alguém contando a própria história.
RELATO_HARM = ["F", "C", "Dm", "Bb"]
KEYS = {"C": -2, "C#": -1, "Db": -1, "D": 0, "D#": 1, "Eb": 1, "E": 2, "F": 3, "F#": 4, "Gb": 4, "G": 5,
        "G#": -6, "Ab": -6, "A": -5, "A#": -4, "Bb": -4, "B": -3}
AMB_LEVEL = {"opening": 0.55, "loss": 0.25, "ritual": 0.18, "price": 0.06, "heroes": 0.25, "tragedy": 0.45,
             "moral": 0.4, "outro": 0.3, "calm": 0.35, "epic": 0.12, "none": 0.3,
             "leve": 0.10, "brisa": 0.06, "pulso": 0.10}


def gerar_tema(seed: int):
    """Seeded 8-bar 3/4 melody over THEME_HARM (two 4-bar phrases, the second echoing the first's rhythm)."""
    rng = np.random.default_rng(seed)
    tones = {"Dm": {2, 5, 9}, "Bb": {10, 2, 5}, "A": {9, 1, 4}, "Gm": {7, 10, 2}}
    scale = [p for p in range(64, 83) if p % 12 in {2, 4, 5, 7, 9, 10, 0}]
    rhythms = [[1, 1, 1], [2, 1], [1, 2], [1, 1, 1]]
    first = [rhythms[rng.integers(0, 4)] for _ in range(3)] + [[3] if rng.random() < 0.5 else [2, 1]]
    bars_r = first + first[:3] + [[3]]
    out, prev, beat = [], 69, 0
    for bar, rh in enumerate(bars_r):
        harm = THEME_HARM[bar]
        pool = [p for p in range(64, 83) if p % 12 in tones[harm]]
        for k, ln in enumerate(rh):
            if bar == 7:
                note = 74  # resolve on D
            elif k == 0:
                near = sorted(pool, key=lambda p: abs(p - prev))[:2]
                note = int(near[rng.integers(0, len(near))])
            else:
                cand = [p for p in scale if 1 <= abs(p - prev) <= 3] or scale
                if harm == "A":
                    cand = [p if p % 12 != 0 else p + 1 for p in cand]  # C -> C# over the dominant
                note = int(cand[rng.integers(0, len(cand))])
            out.append((beat, note, ln))
            prev, beat = note, beat + ln
    return out


class Score:
    def __init__(self, tl, cfg: dict, seed):
        self.tl = tl
        self.D = tl["duration"]
        self.rng = np.random.default_rng(seed)
        self.music, self.box, self.amb, self.sfx = Bus(self.D), Bus(self.D), Bus(self.D), Bus(self.D)
        self.T = KEYS.get(str(cfg.get("key", "D")), 0)
        th = str(cfg.get("theme", "padrao"))
        if th.startswith("gerado"):
            seed_t = int(th.split(":")[1]) if ":" in th else int(cfg.get("seed", 2026))
            self.theme_notes = gerar_tema(seed_t)
        else:
            self.theme_notes = THEME

    # ---- instruments placed on the timeline
    def prog(self, segs, cutoff=1400, gain=0.5, a=1.6, r=2.2, cello=0.24, voices=6):
        for t0, t1, ch in segs:
            if t1 - t0 < 0.05:
                continue
            dur = max(0.2, t1 - t0)
            self.music.add(t0, s.pad_chord([m + self.T for m in CH[ch]], dur, self.rng, cutoff=cutoff, a=a, r=r, gain=gain, voices=voices))
            if cello:
                self.music.add(t0, s.strings_note(BASS[ch] + self.T, dur, self.rng, voices=2, detune_cents=4, cutoff=650,
                                                  a=a * 0.8, r=r, vib=0.004, gain=cello))

    def choir(self, segs, gain=0.22, a=1.6, r=2.0):
        for t0, t1, ch in segs:
            if t1 - t0 < 0.05:
                continue
            for m in CHOIR[ch]:
                self.music.add(t0, s.choir_note(m + self.T, max(0.3, t1 - t0), self.rng, a=a, r=r, gain=gain))

    def theme(self, t0, beat, bars, vel=0.55, bass=True, pad=None):
        first = min(bars)
        for b, m, _ in self.theme_notes:
            bar = b // 3
            if bar in bars:
                t = t0 + (b - 3 * first) * beat
                self.box.add(t, pan(s.musicbox_note(m + self.T, self.rng, vel * self.rng.uniform(0.9, 1.05)), self.rng.uniform(-0.35, 0.35)))
        if bass:
            for bar in bars:
                t = t0 + 3 * (bar - first) * beat
                self.box.add(t, pan(s.musicbox_note(THEME_BASS[bar] + 12 + self.T, self.rng, vel * 0.55), -0.2))
                self.box.add(t + beat, pan(s.musicbox_note(THEME_BASS[bar] + 19 + self.T, self.rng, vel * 0.35), 0.25))
        if pad is not None:
            segs = [(t0 + 3 * (bar - first) * beat, t0 + 3 * (bar - first + 1) * beat, THEME_HARM[bar]) for bar in bars]
            self.prog(segs, **pad)

    def drums(self, t0, t1, bpm0, bpm1, vel0=0.5, vel1=1.0, light=False):
        t, k = t0, 0
        while t < t1:
            u = (t - t0) / max(1e-6, t1 - t0)
            beat = 60 / (bpm0 + (bpm1 - bpm0) * u)
            v = vel0 + (vel1 - vel0) * u
            pos = k % 4
            if light:
                if pos in (0, 2):
                    self.music.add(t, pan(s.taiko(self.rng, v * (1.0 if pos == 0 else 0.7), 64), 0.0))
            elif pos == 0:
                self.music.add(t, pan(s.taiko(self.rng, v, 60), -0.1))
            elif pos == 1:
                self.music.add(t, pan(s.rim(self.rng, v * 0.8), 0.35))
                self.music.add(t + beat / 2, pan(s.taiko(self.rng, v * 0.55, 92), 0.25))
            elif pos == 2:
                self.music.add(t, pan(s.taiko(self.rng, v * 0.85, 64), -0.2))
            else:
                self.music.add(t, pan(s.taiko(self.rng, v * 0.6, 88), 0.2))
                if u > 0.5:
                    self.music.add(t + beat / 2, pan(s.taiko(self.rng, v * 0.5, 96), 0.3))
            t += beat
            k += 1

    def ostinato(self, t0, t1, bpm0, bpm1, gain=0.5):
        pat = [38, 38, 41, 38, 40, 38, 37, 38]
        t, k = t0, 0
        while t < t1:
            u = (t - t0) / max(1e-6, t1 - t0)
            eighth = 30 / (bpm0 + (bpm1 - bpm0) * u)
            x = s.strings_note(pat[k % 8] + self.T, eighth * 0.7, self.rng, voices=3, detune_cents=6, cutoff=520, a=0.008, r=0.12, vib=0, gain=gain)
            self.music.add(t, x)
            t += eighth
            k += 1

    def sfx_at(self, name, t, vel=1.0):
        r = self.rng
        if name == "boom":
            self.sfx.add(t, pan(s.boom(r, vel=0.9 * vel), 0))
        elif name == "hit":
            self.sfx.add(t, pan(s.hit(r, vel=0.85 * vel), 0))
        elif name == "braam":
            self.sfx.add(t, s.braam(r, vel=0.9 * vel))
        elif name == "bell":
            self.sfx.add(t, pan(s.bell(r, f0=146.83 * 2 ** (self.T / 12), vel=0.9 * vel), 0.1))
        elif name == "splat":
            self.sfx.add(t, pan(s.splat(r, vel=0.6 * vel), -0.2))
        elif name == "brush":
            self.sfx.add(t, s.brush(r, vel=0.45 * vel))
        elif name == "heartbeat":
            self.sfx.add(t, pan(s.heartbeat(r, vel=1.0 * vel), 0))
        elif name == "tick":
            self.sfx.add(t, pan(s.tick(r, vel=0.6 * vel), 0.1))
        elif name == "rumble":
            self.sfx.add(t, s.rumble(r, vel=0.55 * vel))
        elif name == "sword":
            self.sfx.add(t, s.sword(r, vel=0.8 * vel))
        elif name == "shimmer":
            self.amb.add(t, s.shimmer(r, 4.0, vel=1.2 * vel, notes=tuple(m + self.T for m in (86, 93, 98, 101))))
        elif name == "swell":
            dur = 2.4
            self.sfx.add(t - dur, s.swell(r, [m + self.T for m in CH["Dm"]], dur, vel=0.6 * vel))
            self.sfx.add(t, pan(s.boom(r, vel=0.45 * vel), 0))
        elif name == "whoosh":
            self.sfx.add(t, s.whoosh(r, 0.9, vel=0.55 * vel))
        else:
            raise ValueError(name)

    def transitions(self):
        for sc in self.tl["scenes"]:
            t0, ty = sc["t0"], sc["transitionIn"]["type"]
            r = self.rng
            if ty == "splatter":
                self.sfx.add(t0 - 0.15, s.whoosh(r, 0.8, 300, 3000, 500, vel=0.45))
            elif ty == "fog":
                self.sfx.add(t0 - 0.2, s.whoosh(r, 1.4, 180, 1400, 300, vel=0.4, p0=0.6, p1=-0.6))
            elif ty == "drip":
                self.sfx.add(t0 + 0.05, s.drips(r, vel=0.9))
                self.sfx.add(t0 - 1.1, s.riser(r, 1.1, vel=0.25))
            elif ty == "slash":
                self.sfx.add(t0 - 0.03, s.slash(r, vel=0.8))
            elif ty == "whip":
                self.sfx.add(t0 - 0.1, s.whoosh(r, 0.45, 500, 5000, 1500, vel=0.6))
            elif ty == "zoomBlur":
                dur = 1.6 if self.tl["format"] == "main" else 0.9
                self.sfx.add(t0 - dur, s.riser(r, dur, vel=0.35))
                self.sfx.add(t0, pan(s.boom(r, vel=0.7), 0))

    # ---- automation & bus processing
    def render(self, music_auto, amb_auto):
        n = self.music.x.shape[1]
        box = self.box.x  # music box: ping-pong delay + long hall
        d = s.secs(0.42)
        echo = np.zeros_like(box)
        echo[0, d:] += box[1, :-d] * 0.32
        echo[1, 2 * d:] += box[0, : -2 * d] * 0.22
        box = box + echo
        box = box * 0.75 + s.reverb(box, s.make_ir(4.5, 4.0, 2800, seed=3, width=1.2), 0.9)
        music = self.music.x + box
        music = music * 0.85 + s.reverb(music, s.make_ir(3.4, 2.8, 2400, seed=5), 0.42)
        music = s.hp(music, 32, order=4)  # trim infrasonics/sub build-up, open the top a bit
        music = s.eq(music, ("lowshelf", 90, -4.0), ("highshelf", 2500, 5.0))
        sfx = self.sfx.x
        sfx = sfx + s.reverb(sfx, s.make_ir(3.8, 3.2, 2200, seed=9), 0.35)
        amb = self.amb.x

        def curve(points):
            ts = np.array([p[0] for p in points]) * SR
            gs = np.array([p[1] for p in points])
            return np.interp(np.arange(n), ts, gs).astype(np.float32)

        music *= curve(music_auto)[None]
        amb *= curve(amb_auto)[None]
        end = s.secs(self.D)
        for x in (music, amb, sfx):
            x[:, end:] = 0
        return music[:, :end], amb[:, :end], sfx[:, :end]


# =================================================================== scene helpers
class Cena:
    def __init__(self, sc: dict, tl: dict, nxt: dict | None):
        self.sc, self.nxt = sc, nxt
        self.t0, self.t1 = sc["t0"], sc["t1"]
        self.L = sc["lines"]
        self.sfx = [c for c in tl["sfx"] if c["scene"] == sc["id"]]

    def by(self, *screens):
        return next((l for l in self.L if l["screen"] in screens), None)

    def bullets(self):
        return [l for l in self.L if l["screen"].startswith(("bullet", "caption"))]

    @property
    def title(self):
        return self.by("title") or self.L[0]

    @property
    def quote(self):
        return self.by("quote") or self.L[-1]

    def impact(self, *names, default=None):
        for nm in names:
            c = next((c for c in self.sfx if c["name"] == nm), None)
            if c:
                return c["t"]
        return default

    @property
    def next_t0(self):
        return self.nxt["t0"] if self.nxt else self.t1


def t(l):
    return l["t"]


def te(l):
    return l["t"] + l["dur"]


def word_t(l, w, default=None):
    return next((x["t"] for x in l["words"] if norm(x["w"]) == norm(w)), default if default is not None else l["t"] + l["dur"] * 0.5)


def spans(lines, chords, start, end):
    """One chord per line, from each line's start to the next one's (first from `start`)."""
    segs = []
    for i, l in enumerate(lines):
        a = start if i == 0 else t(l)
        b = t(lines[i + 1]) if i + 1 < len(lines) else end
        segs.append((a, b, chords[i]))
    return segs


# =================================================================== presets
def p_opening(sc: Score, C: Cena, fmt):
    if fmt == "main":
        beat = 0.79
        t_theme = t(C.L[1]) if len(C.L) > 1 else C.t0 + 2.0
        sc.prog([(C.t0 + 1.0, t_theme, "Dm")], cutoff=900, gain=0.42, a=3.2)
        sc.theme(t_theme, beat, range(0, 4), vel=0.6, pad=dict(cutoff=1150, gain=0.42, a=1.4, r=2.4))
        t_bar4 = t_theme + 9 * beat
        sc.prog([(t_bar4 + 3 * beat, C.next_t0 + 0.4, "Dm")], cutoff=1000, gain=0.38, a=2.0)
    else:
        sc.theme(C.t0 + 0.2, 0.62, range(0, 4), vel=0.55, pad=dict(cutoff=1100, gain=0.4, a=0.6, r=1.6))


def p_loss(sc: Score, C: Cena, fmt):
    q = C.quote
    body = [l for l in C.L if l is not q][: C.L.index(q)]
    if fmt == "main":
        imp = C.impact("hit")
        segs = []
        for i, l in enumerate(body):
            a = C.t0 if i == 0 else t(l)
            b = t(body[i + 1]) if i + 1 < len(body) else t(q)
            if i == len(body) - 1 and len(body) > 1:
                mid = imp if (imp is not None and a < imp < b) else min(b, te(l))
                segs += [(a, mid, "Asus4"), (mid, b, "A")]
            else:
                segs.append((a, b, ["Dm", "Bb", "Gm"][i % 3]))
        segs += [(t(q), te(q), "Dm9"), (te(q), C.t1 + 0.6, "Bb")]
        sc.prog(segs, cutoff=1300, gain=0.42, a=1.8)
        sc.theme(t(q) + 0.25, 0.95, range(0, 2), vel=0.38, bass=False)
    else:
        imp = C.impact("hit", default=t(C.L[-1]))
        second = t(C.L[1]) if len(C.L) > 1 else imp
        sc.prog([(C.t0, second, "Bb"), (second, imp, "Gm"), (imp, C.t1 + 0.3, "A")], cutoff=1400, gain=0.4, a=0.5, r=1.2)


def p_ritual(sc: Score, C: Cena, fmt):
    q, stmt, bl = C.quote, C.by("statement"), C.bullets()
    imp = C.impact("braam", default=t(q) + q["dur"] * 0.6)
    after_b = t(stmt) if stmt else t(q)
    if fmt == "main":
        segs = [(C.t0, t(bl[0]) if bl else after_b, "Dm9")]
        if bl:
            chords = [["Ebmaj7", "Dm9"][i % 2] for i in range(len(bl) - 1)] + ["C#dim7"]
            segs += spans(bl, chords, t(bl[0]), after_b)
        if stmt:
            segs += [(t(stmt), t(stmt) + 2.1, "Bbmaj7"), (t(stmt) + 2.1, t(q), "Gm")]
        segs += [(t(q), imp, "A")]
        sc.prog(segs, cutoff=1150, gain=0.4, a=1.5)
        sc.choir([x for x in segs if x[2] in ("C#dim7", "Bbmaj7", "Gm", "A")], gain=0.2)
        sc.prog([(imp, C.t1 + 0.3, "Dm")], cutoff=650, gain=0.45, a=0.3)
        sc.amb.add(C.t0 + 0.5, s.shimmer(sc.rng, max(1.0, after_b - C.t0), vel=0.9, notes=tuple(m + sc.T for m in (86, 93, 98, 101))))
    else:
        segs = [(C.t0, t(bl[0]) if bl else t(q), "Dm9")]
        if bl:
            segs += [(t(bl[0]), t(bl[-1]), "Ebmaj7"), (t(bl[-1]), t(q), "C#dim7")]
        segs += [(t(q), imp, "A")]
        sc.prog(segs, cutoff=1200, gain=0.4, a=0.5, r=1.0)
        sc.choir(segs[-2:], gain=0.2, a=0.6, r=1.0)
        sc.prog([(imp, C.t1 + 0.2, "Dm")], cutoff=650, gain=0.45, a=0.2, r=0.8)


def p_price(sc: Score, C: Cena, fmt):
    q, stmt, bl, title = C.quote, C.by("statement"), C.bullets(), C.title
    if fmt == "main":
        t_d0, t_d1 = t(title), t(q) - 0.15
        sc.drums(t_d0, t_d1, 84, 118, 0.45, 1.0)
        b1 = t(bl[0]) if bl else t_d0
        sc.ostinato(b1, t_d1, 84 + 34 * (b1 - t_d0) / max(1e-6, t_d1 - t_d0), 118, gain=0.5)
        segs = [(C.t0, b1, "Dm")]
        if bl:
            segs += spans(bl, [["Bb", "C", "A"][i % 3] for i in range(len(bl))], b1, t(stmt) if stmt else t_d1)
        if stmt:
            segs += [(t(stmt), t(stmt) + 1.7, "Dm"), (t(stmt) + 1.7, t_d1, "A7")]
        sc.prog(segs, cutoff=1250, gain=0.4, a=0.9, r=0.35)
        sc.sfx.add(t_d1 - 3.0, s.riser(sc.rng, 3.0, vel=0.4))
        sc.amb.add(C.t0, s.fire(sc.rng, te(q) - C.t0 + 0.3, vel=0.5))
        sc.music.add(t(q) - 0.1, s.strings_note(81 + sc.T, 1.6, sc.rng, voices=3, cutoff=3500, a=0.4, r=0.3, gain=0.1))
        return te(q) + 0.06
    t_d1 = t(q) - 0.1
    sc.drums(t(title) - 0.2, t_d1, 100, 124, 0.55, 1.0)
    b1 = t(bl[0]) if bl else t(title)
    sc.ostinato(b1, t_d1, 108, 124, gain=0.5)
    chords = [["Bb", "C"][i % 2] for i in range(len(bl) - 1)] + ["A7"] if bl else []
    sc.prog([(C.t0, b1, "Dm")] + spans(bl, chords, b1, t_d1), cutoff=1250, gain=0.4, a=0.4, r=0.3)
    sc.amb.add(C.t0, s.fire(sc.rng, te(q) - C.t0, vel=0.5))
    return te(q) + 0.05


def p_heroes(sc: Score, C: Cena, fmt):
    q, title = C.quote, C.title
    body = [l for l in C.L if l is not q and l is not title]
    if fmt == "main":
        chord_lines = body[:-1] if len(body) >= 2 else body
        t_resp = t(body[-1]) if len(body) >= 2 else t(q)
        segs = [(C.t0, t(chord_lines[0]) if chord_lines else t_resp, "Gm")]
        for i, l in enumerate(chord_lines):
            b = t(chord_lines[i + 1]) if i + 1 < len(chord_lines) else t_resp
            if i == len(chord_lines) - 1:
                segs += [(t(l), t(l) + 1.9, "Bb"), (t(l) + 1.9, b, "A")]
            else:
                segs.append((t(l), b, ["Ebmaj7", "Gm"][i % 2]))
        sc.prog(segs, cutoff=1700, gain=0.4, a=1.0, r=1.4)
        sc.drums(t(title), te(chord_lines[-1] if chord_lines else title), 88, 92, 0.35, 0.5, light=True)
        sc.music.add(t_resp, s.strings_note(81 + sc.T, te(q) - t_resp + 0.5, sc.rng, voices=3, cutoff=3200, a=1.2, r=2.0, gain=0.11))
        sc.music.add(te(q) + 0.25, pan(s.piano_low(38 + sc.T, sc.rng, 7.0, 1.0), 0))
        sc.music.add(te(q) + 0.25, pan(s.piano_low(50 + sc.T, sc.rng, 6.0, 0.5), 0.15))
    else:
        sc.prog([(C.t0 + 0.2, t(q), "Gm")], cutoff=1600, gain=0.38, a=0.4, r=1.0)
        sc.music.add(t(q), s.strings_note(81 + sc.T, te(q) - t(q) + 0.4, sc.rng, voices=3, cutoff=3200, a=0.6, r=1.0, gain=0.11))


def p_tragedy(sc: Score, C: Cena, fmt):
    q = C.by("quote") or next((l for l in C.L if any(c["name"] == "swell" and abs(c["t"] - t(l)) < 0.5 for c in C.sfx)), C.L[-1])
    fin = C.by("final")
    t_ela = t(q)
    if fmt == "main":
        bar1 = C.t0 + 0.25
        # the theme's resolution (beat 21 of 8 bars) lands on the quote; fewer bars when the scene is short
        for bars, climax in ((range(0, 8), 21), (range(4, 8), 9), (range(5, 8), 6)):
            beat = (t_ela - bar1) / climax
            if beat >= 0.55:
                break
        sc.theme(bar1, beat, bars, vel=0.5, pad=dict(cutoff=1300, gain=0.38, a=1.6, r=2.4))
        top = bar1 + climax * beat
        segs = [(top - 9 * beat, top - 6 * beat, "Bb"), (top - 6 * beat, top - 3 * beat, "Gm"), (top - 3 * beat, t_ela, "A")]
        sc.choir([x for x in segs if x[0] >= bar1 - 1e-6], gain=0.18)
        t_f = t(fin) if fin else C.t1 - 0.6
        sc.prog([(t_ela, t_f, "Dm")], cutoff=2200, gain=0.5, a=0.4, r=2.5)
        sc.choir([(t_ela, t_f, "Dm")], gain=0.3, a=0.5)
        if fin:
            sc.prog([(t_f, C.t1 - 0.6, "Bbmaj7")], cutoff=900, gain=0.32, a=2.0, r=2.5)
            t_n = word_t(fin, fin.get("hlFrom", ""), default=t(fin) + fin["dur"] * 0.5) if fin.get("hlFrom") else t(fin) + fin["dur"] * 0.5
            for i, m in enumerate([69, 74, 76]):
                sc.box.add(t_n - 0.2 + i * 0.85, pan(s.musicbox_note(m + sc.T, sc.rng, 0.4), 0.2 * (i - 1)))
    else:
        b5 = (t_ela - (C.t0 + 0.2)) / 6.0
        sc.theme(C.t0 + 0.2, b5, range(5, 8), vel=0.5, pad=dict(cutoff=1400, gain=0.38, a=0.6, r=1.4))
        sc.prog([(t_ela, C.t1 + 0.2, "Dm")], cutoff=2200, gain=0.5, a=0.3, r=1.4)
        sc.choir([(t_ela, C.t1, "Dm")], gain=0.28, a=0.3, r=1.2)


def p_moral(sc: Score, C: Cena, fmt):
    last, firsts = C.L[-1], C.L[:-1]
    if fmt == "main":
        segs = [(C.t0, t(firsts[0]), "Dm"), (t(firsts[0]), t(firsts[0]) + 2.0, "Bb"), (t(firsts[0]) + 2.0, t(last), "Gm")] if firsts else [(C.t0, t(last), "Dm")]
        t_m2, t_m2e = t(last), te(last)
        segs += [(t_m2, t_m2 + 1.7, "Asus4"), (t_m2 + 1.7, t_m2e, "A"), (t_m2e, C.t1 + 1.5, "Dm9")]
        sc.prog(segs, cutoff=1400, gain=0.42, a=1.4)
        sc.choir([(t_m2, t_m2 + 1.7, "Asus4"), (t_m2 + 1.7, t_m2e, "A"), (t_m2e, C.t1 + 1.0, "Dm9")], gain=0.2)
        sc.amb.add(t_m2e, s.shimmer(sc.rng, 4.5, vel=1.0, notes=tuple(m + sc.T for m in (86, 93, 98, 101))))
    else:
        t_m, t_me = t(last), te(last)
        tail = min(C.t1 + 0.5, sc.D - 0.3)
        sc.prog([(C.t0, t_m + 1.3, "Bb"), (t_m + 1.3, t_m + 2.6, "Gm"), (t_m + 2.6, t_me, "A"), (t_me, tail, "Dm9")],
                cutoff=1400, gain=0.42, a=0.5, r=1.2)
        sc.choir([(t_m + 2.6, t_me, "A"), (t_me, tail, "Dm9")], gain=0.2, a=0.5, r=1.0)


def p_outro(sc: Score, C: Cena, fmt):
    b8 = 60 / 66
    t_o = C.t0 + 0.5
    sc.theme(t_o, b8, range(0, 4), vel=0.45)
    t_last = t_o + 12 * b8
    sc.box.add(t_last, pan(s.musicbox_note(74 + sc.T, sc.rng, 0.45, dur=5.0), 0))
    sc.box.add(t_last, pan(s.musicbox_note(62 + sc.T, sc.rng, 0.25, dur=5.0), -0.2))
    sc.prog([(C.t0, t_o + 3 * b8, "Dm"), (t_o + 3 * b8, t_o + 6 * b8, "Bb"), (t_o + 6 * b8, t_o + 9 * b8, "A"),
             (t_o + 9 * b8, t_last, "Dm"), (t_last, min(C.t1, sc.D) - 2.0, "Dm9")], cutoff=900, gain=0.34, a=1.6, r=3.0)


def p_calm(sc: Score, C: Cena, fmt):
    chords = [["Dm", "Bb", "F", "C"][i % 4] for i in range(len(C.L))]
    sc.prog(spans(C.L, chords, C.t0, C.next_t0 + 0.3), cutoff=1000, gain=0.36, a=2.0 if fmt == "main" else 0.8, r=2.5)
    for l, ch in zip(C.L, chords):
        m = CHOIR[ch][int(sc.rng.integers(0, 3))] + 12
        sc.box.add(t(l) + 0.1, pan(s.musicbox_note(m + sc.T, sc.rng, 0.3), float(sc.rng.uniform(-0.3, 0.3))))


def _relato_pad(sc: Score, C: Cena, fmt, gain, cutoff, voices, a, r):
    """Pad claro em Fá maior, sem violoncelo — a base comum de leve/brisa/pulso."""
    chords = [RELATO_HARM[i % 4] for i in range(len(C.L))]
    sc.prog(spans(C.L, chords, C.t0, C.next_t0 + 0.3), cutoff=cutoff, gain=gain,
            a=a if fmt == "main" else a * 0.5, r=r, cello=0.0, voices=voices)
    return chords


def p_leve(sc: Score, C: Cena, fmt):
    """Relato pessoal, jovial: pop maior, caixinha nas viradas, sem percussão nem coro."""
    chords = _relato_pad(sc, C, fmt, gain=0.30, cutoff=2400, voices=4, a=0.9, r=1.8)
    for l, ch in zip(C.L, chords):
        m = CHOIR[ch][int(sc.rng.integers(0, 3))] + 12
        sc.box.add(t(l) + 0.1, pan(s.musicbox_note(m + sc.T, sc.rng, 0.26), float(sc.rng.uniform(-0.3, 0.3))))


def p_brisa(sc: Score, C: Cena, fmt):
    """O mais discreto: quase só caixinha sobre um véu de cordas agudas. Para deixar a fala respirar."""
    chords = _relato_pad(sc, C, fmt, gain=0.16, cutoff=3000, voices=3, a=1.6, r=2.6)
    for l, ch in zip(C.L, chords):
        for j, m in enumerate(CHOIR[ch][:2]):
            sc.box.add(t(l) + 0.1 + j * 0.22,
                       pan(s.musicbox_note(m + 12 + sc.T, sc.rng, 0.20), float(sc.rng.uniform(-0.35, 0.35))))


def p_pulso(sc: Score, C: Cena, fmt):
    """leve com um pulso de rim shaker — movimento para montagem, sem peso de tambor."""
    p_leve(sc, C, fmt)
    beat = 60 / 96
    tt, k, t1 = C.t0 + 0.3, 0, min(C.t1, sc.D) - 0.3
    while tt < t1:
        if k % 4 in (1, 3):
            sc.music.add(tt, pan(s.rim(sc.rng, 0.22 if k % 4 == 1 else 0.15), 0.3))
        tt += beat
        k += 1


def p_epic(sc: Score, C: Cena, fmt):
    sc.drums(C.t0 + 0.4, C.t1 - 0.4, 90, 112, 0.5, 0.95)
    chords = [["Dm", "Bb", "Gm", "A"][i % 4] for i in range(len(C.L))]
    segs = spans(C.L, chords, C.t0, C.next_t0 + 0.2)
    sc.prog(segs, cutoff=1600, gain=0.42, a=0.6, r=1.0)
    sc.choir(segs, gain=0.18, a=0.6, r=1.0)


PRESETS = {"opening": p_opening, "loss": p_loss, "ritual": p_ritual, "price": p_price, "heroes": p_heroes,
           "tragedy": p_tragedy, "moral": p_moral, "outro": p_outro, "calm": p_calm, "epic": p_epic,
           "leve": p_leve, "brisa": p_brisa, "pulso": p_pulso,
           "none": lambda *a: None}


# =================================================================== composition
def compose(tl: dict, cfg: dict):
    fmt = tl["format"]
    seed = int(cfg.get("seed", 2026))
    sc = Score(tl, cfg, seed=seed if fmt == "main" else seed + 1)
    D, r = sc.D, sc.rng
    if cfg.get("ambience", "wind") == "wind":
        sc.amb.add(0, s.wind(r, D + 1, vel=1.0))
    if cfg.get("drone", True):
        if fmt == "main":
            sc.music.add(0.5, s.drone(r, D, root=38 + sc.T, vel=0.32, a=3.5, r=4.0))
        else:
            sc.music.add(0.0, s.drone(r, D, root=38 + sc.T, vel=0.32, a=0.8, r=2.0))
    scenes = tl["scenes"]
    cuts = []
    for i, scn in enumerate(scenes):
        nxt = scenes[i + 1] if i + 1 < len(scenes) else None
        C = Cena(scn, tl, nxt)
        cut = PRESETS[scn.get("music") or "calm"](sc, C, fmt)
        if cut is None and (scn.get("transitionOut") or {}).get("type") == "cutBlack":
            cut = te(C.L[-1]) + 0.06
        if cut is not None and nxt is not None:
            cuts.append((cut, nxt["t0"] - 0.02, scn, nxt))
    for cue in tl["sfx"]:
        sc.sfx_at(cue["name"], cue["t"], cue.get("vel", 1.0))
    sc.transitions()

    fade = 5.0 if fmt == "main" else 1.2
    music_auto = [(0, 1)]
    for c0, c1, _, _ in cuts:
        music_auto += [(c0 - 0.02, 1), (c0 + 0.04, 0), (c1, 0), (c1 + 0.05, 1)]
    music_auto += [(D - fade, 1), (D, 0)]
    lvl = lambda x: AMB_LEVEL.get(x.get("music") or "calm", 0.3) * (1.0 if fmt == "main" else 0.8)  # noqa: E731
    amb_auto = [(0, 0)]
    for i, scn in enumerate(scenes):
        amb_auto.append((scn["t0"] + (2.5 if i == 0 and fmt == "main" else 0.8 if fmt == "main" else 0.3), lvl(scn)))
    for c0, c1, a, b in cuts:
        amb_auto += [(c0 - 0.02, lvl(a)), (c0 + 0.04, 0), (c1, 0), (c1 + 0.4, lvl(b))]
    amb_auto += [(D - fade, 0.3), (D, 0)]
    amb_auto.sort(key=lambda p: p[0])
    return sc.render(music_auto, amb_auto)


def gerar(p: Projeto, fmts=None):
    for fmt in fmts or p.formatos():
        tl = json.loads(p.timeline_path(fmt).read_text())
        music, amb, sfx = compose(tl, p.cfg["music"])
        out = p.work / f"stems_{fmt}"
        out.mkdir(parents=True, exist_ok=True)
        for name, x in [("music", music), ("amb", amb), ("sfx", sfx)]:
            wavfile.write(out / f"{name}.wav", SR, x.T.astype(np.float32))
            pk = np.abs(x).max()
            print(f"[{fmt}] {name}: {x.shape[1] / SR:.2f}s pico {20 * np.log10(pk + 1e-9):.1f} dBFS")
