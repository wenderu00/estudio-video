"""Narration: one edge-tts call per script line, cached by (voice, rate, pitch, text).

Writes .estudio/tts/<key>.wav (48 kHz mono float32, silence-trimmed) and <key>.json (duration +
word timings relative to the trimmed audio). edge-tts is an unofficial client of Microsoft Edge's
online read-aloud service: the script text is sent to it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

import numpy as np
from scipy.io import wavfile

from ambiente import ffmpeg
from projeto import Projeto

SR = 48000


def voice_cfg(v: dict) -> dict:
    return {"voice": v["voice"], "rate": v.get("rate", "+0%"), "pitch": v.get("pitch", "+0Hz")}


def line_key(v: dict, text: str) -> str:
    v = voice_cfg(v)
    return hashlib.sha1(f"{v['voice']}|{v['rate']}|{v['pitch']}|{text}".encode()).hexdigest()[:14]


def all_lines(p: Projeto):
    """Unique (key, voice cfg, text, line id) across the project's scripts."""
    seen = {}
    for fmt in p.formatos():
        data = p.roteiro(fmt)
        for sc in data["scenes"]:
            for ln in sc["lines"]:
                v = voice_cfg(data["voices"][ln["speaker"]])
                seen[line_key(v, ln["text"])] = (v, ln["text"], ln["id"])
    return seen


def onset_offset(x: np.ndarray, thr_db=-42.0):
    """First/last sample above threshold (10 ms RMS windows, threshold relative to peak RMS)."""
    win = SR // 100
    n = len(x) // win
    rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    act = np.where(20 * np.log10(rms / rms.max() + 1e-12) > thr_db)[0]
    if len(act) == 0:
        return 0, len(x)
    return act[0] * win, (act[-1] + 1) * win


async def synth_one(cache, key, v, text, sem):
    import edge_tts

    wav_p, json_p = cache / f"{key}.wav", cache / f"{key}.json"
    if wav_p.exists() and json_p.exists():
        return key, "cached"
    async with sem:
        for attempt in range(4):
            try:
                comm = edge_tts.Communicate(text, v["voice"], rate=v["rate"], pitch=v["pitch"], boundary="WordBoundary")
                audio, words = bytearray(), []
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        audio += ch["data"]
                    elif ch["type"] == "WordBoundary":
                        words.append({"w": ch["text"], "t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7})
                if not audio:
                    raise RuntimeError("sem áudio")
                break
            except Exception as e:  # network hiccups
                if attempt == 3:
                    raise RuntimeError(f"edge-tts falhou para “{text[:40]}…”: {e}") from e
                print(f"  nova tentativa {key}: {e}")
                await asyncio.sleep(2 + attempt * 2)
    mp3, raw = cache / f"{key}.mp3", cache / f"{key}.raw.wav"
    mp3.write_bytes(bytes(audio))
    await asyncio.to_thread(ffmpeg, "-i", str(mp3), "-ar", str(SR), "-ac", "1", "-c:a", "pcm_f32le", str(raw))
    _, x = wavfile.read(raw)
    x = x.astype(np.float32)
    a, b = onset_offset(x)
    pre, post = int(0.03 * SR), int(0.09 * SR)
    s0, s1 = max(0, a - pre), min(len(x), b + post)
    y = x[s0:s1].copy()
    f = int(0.006 * SR)  # short fades to avoid clicks
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    wavfile.write(wav_p, SR, y)
    if words:  # anchor first word to detected onset (cancels MP3 decoder delay)
        base, onset_rel = words[0]["t"], (a - s0) / SR
        for w in words:
            w["t"] = round(w["t"] - base + onset_rel, 4)
            w["d"] = round(w["d"], 4)
    meta = {"key": key, "text": text, "voice": v, "dur": round(len(y) / SR, 4), "words": words}
    json_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    raw.unlink(missing_ok=True)
    mp3.unlink(missing_ok=True)
    return key, "new"


async def _main(p: Projeto):
    p.tts.mkdir(parents=True, exist_ok=True)
    lines = all_lines(p)
    sem = asyncio.Semaphore(4)
    res = await asyncio.gather(*(synth_one(p.tts, k, v, t, sem) for k, (v, t, _) in lines.items()))
    new = sum(1 for _, s in res if s == "new")
    print(f"{len(res)} falas ({new} novas)")
    total = 0.0
    for k, (v, t, lid) in lines.items():
        m = json.loads((p.tts / f"{k}.json").read_text())
        total += m["dur"]
        print(f"  {lid:8s} {m['dur']:6.2f}s  {len(m['words']):2d}p  {v['voice'].split('-')[2][:10]:10s} {t}")
    print(f"fala total (únicas): {total:.1f}s")


def gerar(p: Projeto):
    asyncio.run(_main(p))
