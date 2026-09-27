"""Engine environment: persistent data dir, Remotion template sync, external tools
(Real-ESRGAN, depth model, ffmpeg) and requirement checks.

The data dir defaults to ${CLAUDE_PLUGIN_DATA} of this plugin (~/.claude/plugins/data/
estudio-video-estudio-video); the skills pass it explicitly through ESTUDIO_DADOS.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

MOTOR = Path(__file__).resolve().parent.parent  # <plugin>/motor
VIDEO_SRC = MOTOR / "video"  # Remotion template shipped with the plugin
PLUGIN_ID = "estudio-video-estudio-video"

REALESRGAN_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
                  "realesrgan-ncnn-vulkan-20220424-ubuntu.zip")
DEPTH_URL = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model.onnx"
FFMPEG_URL = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
ROSTO_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
             "face_detection_yunet_2023mar.onnx")
# Typefaces for the burned captions (SIL OFL), so a caption does not depend on what the machine
# happens to have installed. Static TTFs on purpose: libass handles variable fonts poorly.
TIPOGRAFIAS_URL = {
    "Barlow-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/barlow/Barlow-Bold.ttf",
    "Anton-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf",
    "ArchivoBlack-Regular.ttf":
        "https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf",
}
FLATPAK_APP = "org.kde.kdenlive"
SYNC_SKIP = {"node_modules", "out", ".cache", "build"}


def dados_padrao() -> Path:
    env = os.environ.get("ESTUDIO_DADOS")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".claude" / "plugins" / "data" / PLUGIN_ID


class Ambiente:
    def __init__(self, dados: Path | None = None):
        self.dados = (dados or dados_padrao()).expanduser().resolve()
        self.video = self.dados / "video"
        self.ferramentas = self.dados / "ferramentas"

    @property
    def realesrgan(self) -> Path:
        return self.ferramentas / "realesrgan" / "realesrgan-ncnn-vulkan"

    @property
    def realesrgan_modelos(self) -> Path:
        return self.ferramentas / "realesrgan" / "models"

    @property
    def modelo_profundidade(self) -> Path:
        return self.ferramentas / "depth_anything_v2_small.onnx"

    @property
    def tipografias(self) -> Path:
        """Fonts shipped for the captions (not to be confused with `_fontes`, the template files)."""
        return self.ferramentas / "tipografias"

    @property
    def tipografias_ok(self) -> bool:
        return all((self.tipografias / n).exists() for n in TIPOGRAFIAS_URL)

    @property
    def modelo_rosto(self) -> Path:
        """YuNet (video mode): where the person is, so the default camera move follows them."""
        return self.ferramentas / "face_detection_yunet.onnx"

    @property
    def whisper(self) -> Path:
        """Where the transcription models live (video mode)."""
        return self.ferramentas / "whisper"

    def whisper_ok(self) -> bool:
        return self.whisper.is_dir() and any(self.whisper.rglob("model.bin"))

    def instalar_whisper(self, nome: str = "medium"):
        """Downloads (once) and warms the faster-whisper model into the data dir."""
        from faster_whisper import WhisperModel

        self.whisper.mkdir(parents=True, exist_ok=True)
        print(f"· preparando o modelo de transcrição `{nome}` (baixa ~1,5 GB na primeira vez) …", flush=True)
        WhisperModel(nome, device="cpu", compute_type="int8", download_root=str(self.whisper))

    # ---------------------------------------------------------------- template sync
    def _fontes(self):
        for p in sorted(VIDEO_SRC.rglob("*")):
            rel = p.relative_to(VIDEO_SRC)
            if p.is_file() and not (set(rel.parts) & SYNC_SKIP):
                yield p, rel

    def hash_template(self) -> str:
        h = hashlib.sha1()
        for p, rel in self._fontes():
            h.update(str(rel).encode())
            h.update(p.read_bytes())
        return h.hexdigest()[:16]

    def sincronizar(self, forcar: bool = False) -> bool:
        """Copy the plugin's Remotion template into the data dir (node_modules stays there).
        Returns True when files changed."""
        stamp = self.video / ".sincronizado"
        h = self.hash_template()
        if not forcar and stamp.exists() and stamp.read_text().strip() == h:
            return False
        self.video.mkdir(parents=True, exist_ok=True)
        keep = set()
        for p, rel in self._fontes():
            dst = self.video / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            keep.add(rel)
        # drop stale sources (never node_modules or the stamps)
        for sub in ("src", "tools"):
            for p in sorted((self.video / sub).rglob("*"), reverse=True) if (self.video / sub).exists() else []:
                rel = p.relative_to(self.video)
                if p.is_file() and rel not in keep:
                    p.unlink()
                elif p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
        stamp.write_text(h)
        return True

    def npm_ok(self) -> bool:
        lock = self.video / "package-lock.json"
        stamp = self.video / ".npm-ok"
        if not (self.video / "node_modules" / "remotion").exists() or not stamp.exists():
            return False
        return (not lock.exists()) or stamp.read_text().strip() == sha1(lock)

    def instalar_npm(self):
        lock = self.video / "package-lock.json"
        cmd = ["npm", "ci", "--no-audit", "--no-fund"] if lock.exists() else ["npm", "install", "--no-audit", "--no-fund"]
        print(f"· instalando dependências do Remotion ({' '.join(cmd)}) em {self.video} …", flush=True)
        subprocess.run(cmd, cwd=self.video, check=True)
        (self.video / ".npm-ok").write_text(sha1(lock) if lock.exists() else "sem-lock")

    def garantir_navegador(self):
        print("· garantindo o Chrome headless do Remotion …", flush=True)
        subprocess.run(["npx", "remotion", "browser", "ensure"], cwd=self.video, check=True)

    def preparar_video(self, verbose: bool = True):
        """Sync + npm install when needed. Cheap when everything is current."""
        mudou = self.sincronizar()
        if mudou and verbose:
            print(f"· template do Remotion sincronizado em {self.video}", flush=True)
        if not self.npm_ok():
            self.instalar_npm()

    # ---------------------------------------------------------------- tools
    def instalar_realesrgan(self):
        dst = self.ferramentas / "realesrgan"
        if self.realesrgan.exists() and (self.realesrgan_modelos / "realesrgan-x4plus.bin").exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.dados) as tmp:
            z = Path(tmp) / "realesrgan.zip"
            baixar(REALESRGAN_URL, z, "Real-ESRGAN (~47 MB)")
            with zipfile.ZipFile(z) as zf:
                for info in zf.infolist():
                    name = Path(info.filename).name
                    if name == "realesrgan-ncnn-vulkan":
                        out = self.realesrgan
                    elif name in ("realesrgan-x4plus.param", "realesrgan-x4plus.bin"):
                        out = self.realesrgan_modelos / name
                    else:
                        continue
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(zf.read(info))
        self.realesrgan.chmod(0o755)

    def testar_realesrgan(self) -> tuple[bool, str]:
        if not self.realesrgan.exists():
            return False, "não instalado"
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=self.dados) as tmp:
            src, out = Path(tmp) / "t.png", Path(tmp) / "o.png"
            Image.new("RGB", (32, 32), (120, 60, 30)).save(src)
            try:
                r = subprocess.run([str(self.realesrgan), "-i", str(src), "-o", str(out), "-n", "realesrgan-x4plus",
                                    "-s", "4", "-t", "32", "-m", str(self.realesrgan_modelos)],
                                   capture_output=True, text=True, timeout=120)
            except subprocess.TimeoutExpired:
                return False, "tempo esgotado (GPU/Vulkan)"
            if r.returncode == 0 and out.exists():
                return True, "GPU/Vulkan ok"
            return False, (r.stderr.strip().splitlines() or ["falhou"])[-1][:120]

    def instalar_profundidade(self):
        if self.modelo_profundidade.exists() and self.modelo_profundidade.stat().st_size > 50_000_000:
            return
        self.ferramentas.mkdir(parents=True, exist_ok=True)
        baixar(DEPTH_URL, self.modelo_profundidade, "Depth Anything V2 Small (~99 MB)")

    def instalar_tipografias(self):
        for nome, url in TIPOGRAFIAS_URL.items():
            dst = self.tipografias / nome
            if dst.exists() and dst.stat().st_size > 20_000:
                continue
            baixar(url, dst, f"fonte {nome} (~150 KB)")

    def instalar_rosto(self):
        if self.modelo_rosto.exists() and self.modelo_rosto.stat().st_size > 100_000:
            return
        self.ferramentas.mkdir(parents=True, exist_ok=True)
        baixar(ROSTO_URL, self.modelo_rosto, "YuNet, detector de rosto (~230 KB)")

    def instalar_ffmpeg_estatico(self):
        dst = self.ferramentas / "ffmpeg"
        if (dst / "ffmpeg").exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.dados) as tmp:
            t = Path(tmp) / "ffmpeg.tar.xz"
            baixar(FFMPEG_URL, t, "ffmpeg estático (~40 MB)")
            with tarfile.open(t) as tf:
                for m in tf.getmembers():
                    if Path(m.name).name in ("ffmpeg", "ffprobe") and m.isfile():
                        (dst / Path(m.name).name).write_bytes(tf.extractfile(m).read())
        for n in ("ffmpeg", "ffprobe"):
            (dst / n).chmod(0o755)


# -------------------------------------------------------------------- helpers
def sha1(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:16]


def baixar(url: str, dst: Path, rotulo: str):
    print(f"· baixando {rotulo} …", flush=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "estudio-video"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        got, last = 0, -1
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
            pct = int(got * 100 / total) if total else -1
            if total and pct // 20 != last:
                last = pct // 20
                print(f"  {pct:3d}% ({got >> 20} MB)", flush=True)
    tmp.rename(dst)


_RECURSOS: dict | None = None


def recursos_ffmpeg() -> dict:
    """What the resolved ffmpeg can do — the video mode needs libx264, libass (filtro `subtitles`)
    and `xfade`."""
    global _RECURSOS
    if _RECURSOS is None:
        def tem(flag: str, alvo: str) -> bool:
            r = subprocess.run(_cmd("ffmpeg") + ["-hide_banner", flag], capture_output=True, text=True)
            return any(alvo in ln.split()[1:2] for ln in (r.stdout + r.stderr).splitlines() if len(ln.split()) > 1)
        try:
            _RECURSOS = {"libx264": tem("-encoders", "libx264"), "aac": tem("-encoders", "aac"),
                         "subtitles": tem("-filters", "subtitles"), "xfade": tem("-filters", "xfade"),
                         "lut3d": tem("-filters", "lut3d"), "vignette": tem("-filters", "vignette"),
                         "noise": tem("-filters", "noise"), "zoompan": tem("-filters", "zoompan")}
        except (RuntimeError, OSError):
            _RECURSOS = dict.fromkeys(("libx264", "aac", "subtitles", "xfade", "lut3d", "vignette",
                                       "noise", "zoompan"), False)
    return _RECURSOS


def versao_node() -> tuple[int, str] | None:
    try:
        v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
        return int(v.lstrip("v").split(".")[0]), v
    except (OSError, ValueError):
        return None


def flatpak_ffmpeg_ok() -> bool:
    if not shutil.which("flatpak"):
        return False
    r = subprocess.run(["flatpak", "run", f"--command=ffmpeg", FLATPAK_APP, "-version"], capture_output=True, text=True)
    return r.returncode == 0


# -------------------------------------------------------------------- ffmpeg
_AMB: Ambiente | None = None
_FF: tuple[list[str], str] | None = None


def usar(amb: Ambiente):
    global _AMB, _FF
    _AMB, _FF = amb, None


def ffmpeg_origem() -> tuple[list[str], str]:
    """Command prefix with a {t} placeholder for the tool name, and where it comes from."""
    global _FF
    if _FF is None:
        amb = _AMB or Ambiente()
        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            _FF = (["{t}"], "sistema")
        elif (amb.ferramentas / "ffmpeg" / "ffmpeg").exists():
            _FF = ([str(amb.ferramentas / "ffmpeg" / "{t}")], "estático (ferramentas)")
        elif flatpak_ffmpeg_ok():
            # the flatpak sandbox only sees the home dir, not /tmp
            _FF = (["flatpak", "run", "--command={t}", FLATPAK_APP], f"flatpak {FLATPAK_APP}")
        else:
            raise RuntimeError("ffmpeg não encontrado. Rode `estudio.py setup` (baixa um ffmpeg estático) "
                               "ou instale o ffmpeg no sistema.")
    return _FF


def _cmd(tool: str) -> list[str]:
    base, _ = ffmpeg_origem()
    return [p.format(t=tool) for p in base]


def ffmpeg(*args, quiet: bool = True) -> str:
    cmd = _cmd("ffmpeg") + ["-hide_banner", "-nostdin", "-y"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += [str(a) for a in args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ({res.returncode}): {' '.join(cmd)}\n{res.stderr[-4000:]}")
    return res.stderr


def ffprobe_json(path) -> dict:
    cmd = _cmd("ffprobe") + ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffprobe falhou: {res.stderr}")
    return json.loads(res.stdout)


# -------------------------------------------------------------------- report
def verificar(amb: Ambiente) -> list[tuple[str, bool, str]]:
    out = []
    out.append(("python", sys.version_info >= (3, 12), sys.version.split()[0]))
    nv = versao_node()
    out.append(("node ≥ 18", bool(nv and nv[0] >= 18), nv[1] if nv else "não encontrado"))
    out.append(("npm", bool(shutil.which("npm")), shutil.which("npm") or "não encontrado"))
    try:
        _, origem = ffmpeg_origem()
        out.append(("ffmpeg", True, origem))
    except RuntimeError as e:
        out.append(("ffmpeg", False, str(e)))
    out.append(("template sincronizado", (amb.video / ".sincronizado").exists()
                and (amb.video / ".sincronizado").read_text().strip() == amb.hash_template(), str(amb.video)))
    out.append(("dependências do Remotion", amb.npm_ok(), "node_modules"))
    chrome = amb.video / "node_modules" / ".remotion" / "chrome-headless-shell"
    out.append(("Chrome headless", chrome.exists(), "baixado" if chrome.exists() else "baixa no setup"))
    try:
        rec = recursos_ffmpeg()
        faltando = [k for k, v in rec.items() if not v]
        out.append(("ffmpeg: x264/aac/legendas", not faltando,
                    "ok" if not faltando else f"falta {', '.join(faltando)} — rode `setup` para o ffmpeg estático"))
    except RuntimeError:
        pass
    out.append(("modelo de transcrição", amb.whisper_ok(),
                "instalado" if amb.whisper_ok() else "baixa no primeiro `transcrever` (modo vídeo)"))
    out.append(("Real-ESRGAN", amb.realesrgan.exists(), "instalado" if amb.realesrgan.exists() else "sem ele, ampliação Lanczos"))
    out.append(("modelo de profundidade", amb.modelo_profundidade.exists(),
                "instalado" if amb.modelo_profundidade.exists() else "sem ele, sem paralaxe 2.5D"))
    out.append(("detector de rosto", amb.modelo_rosto.exists(),
                "instalado" if amb.modelo_rosto.exists() else "sem ele, a câmera não segue quem fala"))
    out.append(("fontes das legendas", amb.tipografias_ok,
                f"{len(TIPOGRAFIAS_URL)} instaladas" if amb.tipografias_ok
                else "sem elas, a legenda usa a fonte do sistema"))
    free = shutil.disk_usage(amb.dados if amb.dados.exists() else Path.home()).free / 2**30
    out.append(("disco livre ≥ 3 GB", free >= 3, f"{free:.1f} GB"))
    return out
