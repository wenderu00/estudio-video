"""Raw video sources: probing, audio extraction and silence detection.

The video mode of the studio starts from one or more recordings listed in projeto.json under
`sources`. This module reads their real parameters with ffprobe, extracts the audio the cut list and
the mix will use, and finds the silent spans that feed the cut suggestions.
"""
from __future__ import annotations

import json

import numpy as np
from scipy.io import wavfile

from ambiente import ffmpeg, ffprobe_json
from projeto import Projeto

SR = 48000
SR_ASR = 16000
VID_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


# -------------------------------------------------------------------- probing
def frac(v: str, default: float = 30.0) -> float:
    try:
        num, _, den = str(v).partition("/")
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return default


def info(path) -> dict:
    """fps, size, duration and audio presence of a source file."""
    data = ffprobe_json(path)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise RuntimeError(f"{path}: sem faixa de vídeo")
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"]) % 360
    w, h = int(v["width"]), int(v["height"])
    if rot in (90, 270):
        w, h = h, w
    fps = frac(v.get("avg_frame_rate") or v.get("r_frame_rate"), 30.0) or frac(v.get("r_frame_rate"))
    return {
        "arquivo": str(path),
        "width": w, "height": h, "rotacao": rot,
        "fps": round(fps, 6),
        "dur": round(float(data["format"]["duration"]), 4),
        "codec": v["codec_name"],
        "audio": bool(a),
        "audio_sr": int(a["sample_rate"]) if a else 0,
        "audio_ch": int(a["channels"]) if a else 0,
        "tamanho_mb": round(int(data["format"]["size"]) / 1e6, 1),
    }


def detectar_videos(raiz) -> list[str]:
    """Video files of a project folder, biggest first (the raw recording is normally the big one)."""
    from projeto import natural_key
    cands = []
    for pasta in (raiz, raiz / "bruto", raiz / "fontes"):
        if pasta.is_dir():
            cands += [p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in VID_EXT]
    cands = [p for p in cands if not p.is_relative_to(raiz / "saida")]
    cands.sort(key=natural_key)
    cands.sort(key=lambda p: p.stat().st_size, reverse=True)
    return [str(p.relative_to(raiz)) for p in cands]


# -------------------------------------------------------------------- audio
def extrair_audio(p: Projeto, nome: str, forcar: bool = False) -> tuple:
    """Source audio as mono float32: 48 kHz for the mix, 16 kHz for the transcriber."""
    src = p.fonte(nome)
    p.work.mkdir(parents=True, exist_ok=True)
    full, asr = p.work / f"fonte_{nome}.wav", p.work / f"fonte_{nome}_16k.wav"
    if forcar or not full.exists():
        ffmpeg("-i", str(src), "-vn", "-ar", str(SR), "-ac", "1", "-c:a", "pcm_f32le", str(full))
    if forcar or not asr.exists():
        ffmpeg("-i", str(full), "-ar", str(SR_ASR), "-ac", "1", "-c:a", "pcm_f32le", str(asr))
    return full, asr


def ler_wav(path) -> np.ndarray:
    _, x = wavfile.read(path)
    inteiro = np.issubdtype(x.dtype, np.integer)
    escala = float(np.iinfo(x.dtype).max) if inteiro else 1.0
    x = x.astype(np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    return x / escala if inteiro else x


# -------------------------------------------------------------------- silence
def envelope_db(x: np.ndarray, sr: int = SR, janela: float = 0.02) -> tuple:
    """Per-window RMS in dBFS plus the window length in samples."""
    win = max(1, int(sr * janela))
    n = len(x) // win
    rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-12), win


def silencios(x: np.ndarray, sr: int = SR, thr_rel_db: float = -34.0, minimo: float = 0.35) -> list:
    """Silent spans (t0, t1) longer than `minimo`, with the threshold relative to the speech level."""
    db, win = envelope_db(x, sr)
    if len(db) == 0:
        return []
    fala = np.percentile(db[db > db.max() - 45], 60) if (db > db.max() - 45).any() else db.max()
    thr = fala + thr_rel_db
    quieto = db < thr
    out, i, n = [], 0, len(quieto)
    while i < n:
        if quieto[i]:
            j = i
            while j < n and quieto[j]:
                j += 1
            t0, t1 = i * win / sr, j * win / sr
            if t1 - t0 >= minimo:
                out.append((round(t0, 3), round(t1, 3)))
            i = j
        else:
            i += 1
    return out


# -------------------------------------------------------------------- report
def descrever(p: Projeto) -> dict:
    """Probe every source of the project and cache it in .estudio/fontes.json."""
    fontes = {nome: info(p.fonte(nome)) for nome in p.sources()}
    p.build.mkdir(parents=True, exist_ok=True)
    (p.build / "fontes.json").write_text(json.dumps(fontes, ensure_ascii=False, indent=1))
    return fontes
