"""A video project: the user's files (projeto.json, roteiro*.json, arte.json), build paths,
defaults and validation."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path

FORMATOS = {
    "main": {"arquivo": "roteiro.json", "width": 1920, "height": 1080, "fps": 30, "sufixo": "", "comp": "Main"},
    "shorts": {"arquivo": "roteiro_shorts.json", "width": 1080, "height": 1920, "fps": 30, "sufixo": "-shorts", "comp": "Shorts"},
}
KIND_ALIAS = {"tragedy": "panorama"}
KINDS = {"opening", "chapter", "panorama", "moral", "outro"}
TRANSICOES = {"none", "fadeFromBlack", "crossfade", "splatter", "fog", "drip", "slash", "whip", "zoomBlur"}
SAIDAS = {"cutBlack", "fadeBlack"}
SFX = {"boom", "hit", "braam", "bell", "splat", "brush", "heartbeat", "tick", "rumble", "sword", "shimmer", "swell", "whoosh"}
MUSICAS = {"opening", "loss", "ritual", "price", "heroes", "tragedy", "moral", "outro", "calm", "epic", "none",
           "leve", "brisa", "pulso"}
PARTICULAS = {"embers", "sparks", "ash", "dust", "petals"}
FX_VOZ = {"narrador", "sombrio", "sala", "seco", "gravacao"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MODOS = {"imagens", "video"}
# video mode: how a kept segment enters (ffmpeg side, not the Remotion transitions above).
# The value says whether the incoming segment is drawn OVER the outgoing one — an overlapping
# transition eats `overlapFrames` from both sides, so the totals still add up to durationInFrames.
TRANSICOES_CORTE = {
    "none": False, "corte": False, "fadeFromBlack": False,
    "crossfade": True, "dissolve": True, "granulado": True, "blur": True, "pixel": True,
    "whipLeft": True, "whipRight": True, "zoomPunch": True,
    "sliceH": True, "sliceV": True, "wipeDiagonal": True,
    "radial": True, "circleOpen": True,
    "dipBlack": True, "dipWhite": True,
    "glitch": True, "filmBurn": True, "hazard": True,
}
SAIDAS_CORTE = {"fadeToBlack", "fadeToWhite", "dipToColor"}
# Remotion overlays: short things, so only their frames go through Chrome. A full-length
# watermark or progress bar is NOT here — those are ffmpeg (projeto.json -> brand), or every
# single frame of the video would have to be composited by the browser.
OVERLAYS = {"cartao", "titulo", "destaque", "imagem",
            "secao", "tarja", "callout", "card", "vinheta", "telaFinal"}
# how the camera moves inside a segment (a crop animated over the clip; never changes frame count)
CAMERAS = {"none", "punch", "pull", "hold", "snap"}

# Picture finish. A preset fills the numbers; any field set by hand wins over it. `nenhum` is the
# raw footage (what the engine did before the `look` block existed).
LOOK_PRESETS = {
    "nenhum": {},
    "limpo": {"sharpen": 0.6},
    "natural": {"contrast": 1.06, "saturation": 1.06, "temp": 6, "vignette": 0.26, "grain": 2.0,
                "sharpen": 0.6},
    "quente": {"contrast": 1.08, "saturation": 1.10, "temp": 18, "vignette": 0.30, "grain": 2.5,
               "sharpen": 0.6},
    "frio": {"contrast": 1.08, "saturation": 1.02, "temp": -16, "vignette": 0.30, "grain": 2.5,
             "sharpen": 0.6},
    "cinema": {"contrast": 1.14, "saturation": 0.94, "temp": -6, "vignette": 0.42, "grain": 4.0,
               "sharpen": 0.5, "bloom": 0.18},
}
LOOK_NUMEROS = {"contrast": (0.2, 3.0), "saturation": (0.0, 3.0), "brightness": (-1.0, 1.0),
                "gamma": (0.1, 4.0), "temp": (-100.0, 100.0), "vignette": (0.0, 1.0),
                "grain": (0.0, 40.0), "sharpen": (0.0, 3.0), "bloom": (0.0, 1.0),
                "chroma": (0.0, 20.0)}

# fields an overlay of each kind cannot do without (the others have sensible defaults)
OVERLAY_OBRIGATORIOS = {
    "cartao": ("title",), "titulo": ("title",), "destaque": ("box",), "imagem": ("file",),
    "secao": ("title",), "tarja": ("name",), "callout": ("title",), "card": ("title",),
    "vinheta": (), "telaFinal": (),
}

# on-screen roles ("screen") each scene kind understands, per format; "*" = prefix match
SCREENS = {
    "main": {
        "opening": {"hook*", "label", "title", "brush", "porela"},
        "chapter": {"title", "bullet*", "statement", "quote"},
        "panorama": {"title", "intro", "bullet*", "quoteLead", "quote", "final"},
        "moral": {"line1", "line2"},
        "outro": {"question", "cta"},
    },
    "shorts": {
        "opening": {"hook*"},
        "chapter": {"title", "caption", "quoteLead", "quote"},
        "panorama": {"title", "caption", "quoteLead", "quote"},
        "moral": {"line1", "line2"},
        "outro": {"line1", "line2"},
    },
}

DEFAULT_PROJETO = {
    "title": "",
    "slug": "",
    "modo": "imagens",
    "images": [],
    "sources": {},
    "captions": {
        "font": "DejaVu Sans",
        "font_file": "Barlow-Bold.ttf",
        "size": 52,
        "color": "#FFFFFF",
        "highlight": "#E3263A",
        "outline": 3.5,
        "shadow": 0.8,
        "box": False,
        "bg_opacity": 0.55,
        "position": "bottom",
        "margin": 120,
        "safe_bottom": 0,
        "bold": True,
        "uppercase": False,
        "karaoke": True,
        "pop": True,
        "fade": 120,
        "capitalizar": True,
        "max_chars": 38,
        "max_lines": 2,
        "max_words": 0,
    },
    "look": {"preset": "natural", "lut": None},
    # the default camera move: only where a face is on screen, so a screen capture is never cropped
    "camera": {"auto": True, "zoom": 1.06, "dur_minima": 6.0},
    "brand": {"logo": "", "name": "", "handle": "", "color": "",
              "marca": True, "marca_opacidade": 0.55, "marca_altura": 0.06,
              "progresso": True, "tela_final": 0.0},
    "voice": {"fx": "gravacao"},
    "voices": {
        "narrador": {"voice": "pt-BR-AntonioNeural", "rate": "-8%", "pitch": "-3Hz", "fx": "narrador", "label": "Narrador"},
    },
    "palette": {
        "bg": "#07070A",
        "ink": "#15101A",
        "white": "#EDE6DA",
        "accents": {
            "red": {"color": "#E3263A", "text": "#F4EEE6", "fog": "#b8323f"},
            "purple": {"color": "#A461FF", "text": "#1B0F2A", "fog": "#8f6ad8"},
            "blue": {"color": "#5AA8F0", "text": "#0B1B2E", "fog": "#6f9fd0"},
        },
    },
    "music": {"theme": "padrao", "key": "D", "ambience": "wind", "drone": True, "seed": 2026},
    "mix": {"lufs": -14.0, "voice_lufs": -15.5, "music_lufs": {"main": -22.0, "shorts": -20.5}, "ducking_db": 9.0},
    "render": {"crf": 16, "concurrency": 6, "preset": "slow"},
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


# 12 transposições distintas: KEYS repete enarmônicos (C#/Db, D#/Eb, F#/Gb, G#/Ab, A#/Bb).
TONS = ["G#", "A", "Bb", "B", "C", "C#", "D", "Eb", "E", "F", "F#", "G"]


def musica_do_slug(slug: str) -> dict:
    """Tonalidade e semente próprias de cada projeto — sem isso todo vídeo sai na mesma trilha.

    hashlib, e não hash(), porque o hash de str é aleatorizado por processo: o mesmo projeto
    tem de render sempre a mesma trilha."""
    h = hashlib.sha1(slug.encode("utf-8")).digest()
    return {**DEFAULT_PROJETO["music"],
            "key": TONS[h[0] % len(TONS)],
            "seed": int.from_bytes(h[1:5], "big") % 100000}


def natural_key(p: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)]


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "voices":
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def resolver_look(*camadas) -> dict:
    """A chain of `look` blocks (the project's, then a segment's) flattened into numbers.

    Naming a `preset` in a layer restarts the numbers from that preset; a field written by hand
    always wins over the preset it sits next to."""
    out: dict = {"preset": "nenhum", "lut": None}
    for look in camadas:
        if not isinstance(look, dict):
            continue
        if look.get("preset"):
            out = {"preset": look["preset"], "lut": out.get("lut"), **LOOK_PRESETS.get(look["preset"], {})}
        if "lut" in look:
            out["lut"] = look["lut"] or None
        for k, v in look.items():
            if k in LOOK_NUMEROS and v is not None:
                out[k] = float(v)
    return out


class Projeto:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).expanduser().resolve()
        self.arquivo = self.raiz / "projeto.json"
        user = json.loads(self.arquivo.read_text()) if self.arquivo.exists() else {}
        self.cfg = merge(DEFAULT_PROJETO, user)
        self.build = self.raiz / ".estudio"
        self.saida = self.raiz / "saida"
        self.up = self.build / "up"
        self.public = self.build / "public"
        self.art = self.public / "art"
        self.fx = self.public / "fx"
        self.audio = self.public / "audio"
        self.tts = self.build / "tts"
        self.work = self.build / "work"
        self.grades = self.build / "grades"
        self.quadros = self.build / "quadros"
        self.qa = self.build / "qa"

    # ---------------------------------------------------------------- identity
    @property
    def titulo(self) -> str:
        return self.cfg.get("title") or self.raiz.name

    @property
    def slug(self) -> str:
        return self.cfg.get("slug") or slugify(self.titulo) or "video"

    def existe(self) -> bool:
        return self.arquivo.exists()

    @property
    def modo(self) -> str:
        return self.cfg.get("modo") or "imagens"

    # ---------------------------------------------------------------- inputs
    def sources(self) -> dict:
        return dict(self.cfg.get("sources") or {})

    def fonte_principal(self) -> str:
        src = self.sources()
        if not src:
            raise ValueError(f"projeto.json: nenhuma fonte de vídeo em `sources` ({self.raiz})")
        return "principal" if "principal" in src else next(iter(src))

    def fonte(self, nome: str | None = None) -> Path:
        src = self.sources()
        nome = nome or self.fonte_principal()
        if nome not in src:
            raise ValueError(f"fonte `{nome}` não está em projeto.json (disponíveis: {', '.join(src) or 'nenhuma'})")
        return self.raiz / src[nome]

    def corte_path(self) -> Path:
        return self.raiz / "corte.json"

    def corte(self) -> dict:
        p = self.corte_path()
        return json.loads(p.read_text()) if p.exists() else {"segments": []}

    def transcricao_path(self) -> Path:
        return self.build / "transcricao.json"

    def sugestoes_path(self) -> Path:
        return self.build / "sugestoes.json"

    def imagens(self) -> list[Path]:
        return [self.raiz / p for p in self.cfg.get("images", [])]

    def imagem(self, i: int) -> Path:
        imgs = self.imagens()
        if not 1 <= i <= len(imgs):
            raise ValueError(f"imagem {i} fora da lista de projeto.json (1..{len(imgs)})")
        return imgs[i - 1]

    def roteiro_path(self, fmt: str) -> Path:
        return self.raiz / FORMATOS[fmt]["arquivo"]

    def formatos(self) -> list[str]:
        if self.modo == "video":
            return ["main"]
        return [f for f in FORMATOS if self.roteiro_path(f).exists()]

    def roteiro(self, fmt: str) -> dict:
        data = json.loads(self.roteiro_path(fmt).read_text())
        base = FORMATOS[fmt]
        for k in ("width", "height", "fps"):
            data.setdefault(k, base[k])
        data["format"] = fmt
        data.setdefault("title", self.titulo + (" (Shorts)" if fmt == "shorts" else ""))
        data["voices"] = merge(self.cfg["voices"], data.get("voices", {}))
        for sc in data["scenes"]:
            sc["kind"] = KIND_ALIAS.get(sc.get("kind"), sc.get("kind"))
        return data

    def arte(self) -> dict:
        p = self.raiz / "arte.json"
        return json.loads(p.read_text()) if p.exists() else {"scale": 4, "crops": {}}

    # ---------------------------------------------------------------- outputs
    def timeline_path(self, fmt: str) -> Path:
        return self.build / f"timeline-{fmt}.json"

    def mp4(self, fmt: str) -> Path:
        return self.saida / f"{self.slug}{FORMATOS[fmt]['sufixo']}.mp4"

    def srt(self, fmt: str) -> Path:
        return self.saida / f"{self.slug}{FORMATOS[fmt]['sufixo']}.srt"


def detectar_imagens(raiz: Path) -> list[str]:
    for pasta in (raiz / "imagens", raiz / "images", raiz):
        if pasta.is_dir():
            imgs = sorted((p for p in pasta.iterdir() if p.suffix.lower() in IMG_EXT and p.is_file()), key=natural_key)
            if imgs:
                return [str(p.relative_to(raiz)) for p in imgs]
    return []


# -------------------------------------------------------------------- anchors
ANCHOR_RE = re.compile(r"^(?P<base>.*?)(?P<off>[+-]\d+(?:\.\d+)?)(?P<unit>[sf]?)$")


class AnchorError(ValueError):
    pass


def parse_anchor(spec):
    """-> (base, offset_value, unit) ; base None for plain seconds."""
    if isinstance(spec, (int, float)):
        return None, float(spec), "s"
    s = str(spec).strip()
    try:
        return None, float(s), "s"
    except ValueError:
        pass
    m = ANCHOR_RE.match(s)
    if m and m.group("base"):
        return m.group("base"), float(m.group("off")), (m.group("unit") or "s")
    return s, 0.0, "s"


def find_line(lines: list, ref: str):
    if ref.startswith("@"):
        key = ref[1:]
        return next((l for l in lines if l.get("screen") == key), None)
    return next((l for l in lines if l.get("id") == ref), None)


def split_base(base: str):
    ref, _, word = base.partition(":")
    ref, _, edge = ref.partition(".")
    return ref, edge, word


# -------------------------------------------------------------------- cut-list time
TC_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}(?:[.,]\d+)?)$")  # SS.mmm or M:SS.mmm or H:MM:SS.mmm


def parse_tempo(spec, palavras: list | None = None, fps: float = 30.0) -> float:
    """A time in corte.json: seconds, `M:SS.mmm`, or `w:<índice>[.end]` — each with an optional
    `±<n>` offset in seconds (or `±<n>f` in frames)."""
    base, off, unit = parse_anchor(spec)
    off_s = off / fps if unit == "f" else off
    if base is None:
        return off_s
    base = base.strip()
    if base.startswith("w:"):
        ref, _, edge = base[2:].partition(".")
        if palavras is None:
            raise AnchorError(f"âncora `{spec}` precisa da transcrição (rode `transcrever`)")
        try:
            w = palavras[int(ref)]
        except (ValueError, IndexError):
            raise AnchorError(f"âncora `{spec}` — palavra {ref} não existe na transcrição "
                              f"(0..{len(palavras) - 1})") from None
        if edge not in ("", "end", "start"):
            raise AnchorError(f"âncora `{spec}` — sufixo `.{edge}` inválido (use .end)")
        return float(w["t"] + (w["d"] if edge == "end" else 0.0)) + off_s
    partes = base.replace(",", ".").split(":")
    try:
        if len(partes) == 1:
            return float(partes[0]) + off_s
        segundos = float(partes[-1])
        minutos = float(partes[-2])
        horas = float(partes[-3]) if len(partes) > 2 else 0.0
        return horas * 3600 + minutos * 60 + segundos + off_s
    except ValueError:
        raise AnchorError(f"tempo `{spec}` inválido (use segundos, M:SS.mmm ou w:<índice>)") from None


# -------------------------------------------------------------------- validation
def _screen_ok(screen: str, allowed: set) -> bool:
    return screen in allowed or any(a.endswith("*") and screen.startswith(a[:-1]) for a in allowed)


def _walk_at(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "at":
                yield path, v
            else:
                yield from _walk_at(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_at(v, f"{path}[{i}]")


def _vozes_e_paleta(p: Projeto) -> list[str]:
    erros = []
    for spk, v in p.cfg["voices"].items():
        if "voice" not in v:
            erros.append(f"projeto.json: voz `{spk}` sem campo `voice`")
        if v.get("fx", "narrador") not in FX_VOZ:
            erros.append(f"projeto.json: voz `{spk}` com fx `{v.get('fx')}` desconhecido ({', '.join(sorted(FX_VOZ))})")
    return erros


def _checar_look(look: dict, onde: str, raiz: Path) -> list[str]:
    erros = []
    if not isinstance(look, dict):
        return [f"{onde}: `look` deve ser um objeto"]
    preset = look.get("preset", "natural")
    if preset not in LOOK_PRESETS:
        erros.append(f"{onde}: look.preset `{preset}` inválido ({', '.join(sorted(LOOK_PRESETS))})")
    lut = look.get("lut")
    if lut and not (raiz / str(lut)).exists():
        erros.append(f"{onde}: look.lut `{lut}` não existe")
    for k, v in look.items():
        if k in ("preset", "lut"):
            continue
        if k not in LOOK_NUMEROS:
            erros.append(f"{onde}: look.{k} não existe ({', '.join(sorted(LOOK_NUMEROS))})")
        elif v is not None:
            lo, hi = LOOK_NUMEROS[k]
            if not isinstance(v, (int, float)) or not lo <= float(v) <= hi:
                erros.append(f"{onde}: look.{k} deve ser um número entre {lo:g} e {hi:g}")
    return erros


def _look_e_marca(p: Projeto) -> list[str]:
    erros = _checar_look(p.cfg.get("look") or {}, "projeto.json", p.raiz)
    marca = p.cfg.get("brand") or {}
    logo = str(marca.get("logo") or "")
    if logo and not (p.raiz / logo).exists():
        erros.append(f"projeto.json: brand.logo `{logo}` não existe")
    cor = str(marca.get("color") or "")
    if cor and not re.fullmatch(r"#[0-9A-Fa-f]{6}", cor):
        erros.append("projeto.json: brand.color deve ser uma cor #RRGGBB")
    if not isinstance(marca.get("tela_final", 0.0), (int, float)) or float(marca.get("tela_final", 0.0)) < 0:
        erros.append("projeto.json: brand.tela_final deve ser um número de segundos >= 0 (0 desliga)")
    return erros


def validar_video(p: Projeto) -> tuple[list[str], list[str]]:
    """Video mode: sources, captions and corte.json (the cut list)."""
    erros, avisos = [], []
    fontes = p.sources()
    if not fontes:
        erros.append("projeto.json: nenhuma fonte em `sources` (rode `estudio.py novo --video <arquivo>`)")
    for nome, rel in fontes.items():
        if not (p.raiz / rel).exists():
            erros.append(f"projeto.json: fonte `{nome}` não existe: {rel}")
    cap = p.cfg.get("captions") or {}
    if cap.get("position") not in ("top", "bottom", "center"):
        erros.append(f"projeto.json: captions.position `{cap.get('position')}` inválido (top, bottom, center)")
    if not isinstance(cap.get("size"), (int, float)) or cap["size"] <= 0:
        erros.append("projeto.json: captions.size deve ser um número positivo")
    for k in ("color", "highlight"):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(cap.get(k, ""))):
            erros.append(f"projeto.json: captions.{k} deve ser uma cor #RRGGBB")
    if (p.cfg.get("voice") or {}).get("fx", "gravacao") not in FX_VOZ:
        erros.append(f"projeto.json: voice.fx `{p.cfg['voice'].get('fx')}` desconhecido ({', '.join(sorted(FX_VOZ))})")
    if not isinstance(cap.get("max_words", 0), int) or cap.get("max_words", 0) < 0:
        erros.append("projeto.json: captions.max_words deve ser inteiro >= 0 (0 = legenda em blocos)")
    if not 0.0 <= float(cap.get("bg_opacity", 0.55)) <= 1.0:
        erros.append("projeto.json: captions.bg_opacity deve estar entre 0 e 1")
    camcfg = p.cfg.get("camera") or {}
    if not isinstance(camcfg.get("zoom", 1.06), (int, float)) or not 1.0 <= float(camcfg.get("zoom", 1.06)) <= 2.0:
        erros.append("projeto.json: camera.zoom deve ser um número entre 1.0 e 2.0")
    if not isinstance(camcfg.get("dur_minima", 6.0), (int, float)) or float(camcfg.get("dur_minima", 6.0)) < 0:
        erros.append("projeto.json: camera.dur_minima deve ser um número de segundos >= 0")
    # a bare name is one of the fonts the plugin ships and is only resolved at montagem time;
    # a path has to exist in the project
    ff = str(cap.get("font_file") or "")
    if ff and "/" in ff and not (p.raiz / ff).exists():
        erros.append(f"projeto.json: captions.font_file `{ff}` não existe no projeto")
    erros += _look_e_marca(p)

    durs, fps_fonte = {}, {}
    cache = p.build / "fontes.json"
    if cache.exists():
        for nome, info in json.loads(cache.read_text()).items():
            durs[nome], fps_fonte[nome] = info.get("dur"), info.get("fps")
    fps = float(p.cfg.get("render", {}).get("fps") or fps_fonte.get(p.fonte_principal() if fontes else "", 0) or FORMATOS["main"]["fps"])

    tr = p.transcricao_path()
    palavras = json.loads(tr.read_text())["words"] if tr.exists() else None

    if not p.corte_path().exists():
        erros.append("corte.json não encontrado — o montador escreve a lista de cortes (veja references/corte.md)")
        return erros + _vozes_e_paleta(p), avisos
    try:
        corte = p.corte()
    except json.JSONDecodeError as e:
        return erros + [f"corte.json: JSON inválido: {e}"], avisos
    segs = corte.get("segments") or []
    if not segs:
        erros.append("corte.json: lista `segments` vazia")
    ids, faixas = set(), []
    for i, sg in enumerate(segs):
        sid = sg.get("id") or f"#{i}"
        onde = f"corte.json: segmento `{sid}`"
        if not sg.get("id"):
            erros.append(f"{onde}: sem `id`")
        if sid in ids:
            erros.append(f"{onde}: id repetido")
        ids.add(sid)
        nome = sg.get("source") or (p.fonte_principal() if fontes else None)
        if fontes and nome not in fontes:
            erros.append(f"{onde}: source `{nome}` não está em projeto.json ({', '.join(fontes)})")
        try:
            t0 = parse_tempo(sg.get("in", 0), palavras, fps)
            t1 = parse_tempo(sg.get("out", 0), palavras, fps)
        except AnchorError as e:
            erros.append(f"{onde}: {e}")
            continue
        if t1 <= t0:
            erros.append(f"{onde}: `out` ({t1:.3f}s) não é maior que `in` ({t0:.3f}s)")
            continue
        faixas.append((nome, t0, t1))
        dur = durs.get(nome)
        if dur and t1 > dur + 0.05:
            erros.append(f"{onde}: vai até {t1:.2f}s, além da fonte `{nome}` ({dur:.2f}s)")
        if t0 < -1e-6:
            erros.append(f"{onde}: `in` negativo")
        tin = sg.get("transitionIn", {"type": "none"})
        tipo_in = tin.get("type", "none")
        if tipo_in not in TRANSICOES_CORTE:
            erros.append(f"{onde}: transitionIn `{tipo_in}` inválida ({', '.join(sorted(TRANSICOES_CORTE))})")
        elif tipo_in not in ("none", "corte") and float(tin.get("dur", 0)) <= 0:
            erros.append(f"{onde}: transitionIn `{tipo_in}` precisa de `dur` > 0")
        elif i == 0 and TRANSICOES_CORTE[tipo_in]:
            erros.append(f"{onde}: o primeiro segmento não tem com o que fazer `{tipo_in}` — ela "
                         f"sobrepõe dois segmentos (use fadeFromBlack)")
        tout = sg.get("transitionOut")
        if tout:
            if tout.get("type") not in SAIDAS_CORTE:
                erros.append(f"{onde}: transitionOut `{tout.get('type')}` inválida ({', '.join(sorted(SAIDAS_CORTE))})")
            elif float(tout.get("dur", 0)) <= 0:
                erros.append(f"{onde}: transitionOut precisa de `dur` > 0")
            elif tout["type"] == "dipToColor" and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(tout.get("color", ""))):
                erros.append(f"{onde}: transitionOut `dipToColor` precisa de `color` #RRGGBB")
        if sg.get("music", "calm") not in MUSICAS:
            erros.append(f"{onde}: music `{sg.get('music')}` inválida ({', '.join(sorted(MUSICAS))})")
        if not isinstance(sg.get("speed", 1.0), (int, float)) or not 0.25 <= float(sg.get("speed", 1.0)) <= 4:
            erros.append(f"{onde}: `speed` deve ser um número entre 0.25 e 4")
        if "look" in sg:
            erros += _checar_look(sg["look"], onde, p.raiz)
        cam = sg.get("camera")
        if cam is not None and not isinstance(cam, dict):
            erros.append(f"{onde}: `camera` deve ser um objeto")
        elif cam:
            if cam.get("type", "none") not in CAMERAS:
                erros.append(f"{onde}: camera.type `{cam.get('type')}` inválido ({', '.join(sorted(CAMERAS))})")
            for k in ("from", "to"):
                v = cam.get(k, 1.0)
                if not isinstance(v, (int, float)) or not 1.0 <= float(v) <= 3.0:
                    erros.append(f"{onde}: camera.{k} deve ser um zoom entre 1.0 e 3.0")
            foco = cam.get("focus")
            if foco is not None and not (isinstance(foco, list) and len(foco) == 2
                                         and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in foco)):
                erros.append(f"{onde}: camera.focus deve ser [x, y], cada um entre 0 e 1")
            if cam.get("type") == "snap":
                if cam.get("at") is None:
                    erros.append(f"{onde}: camera `snap` precisa de `at` (o instante do salto)")
                else:
                    try:
                        ats = parse_tempo(cam["at"], palavras, fps)
                        if not (t0 - 1e-6 <= ats <= t1 + 1e-6):
                            erros.append(f"{onde}: camera.at {ats:.2f}s cai fora do segmento ({t0:.2f}–{t1:.2f}s)")
                    except AnchorError as e:
                        erros.append(f"{onde}: camera.at — {e}")
        for j, ov in enumerate(sg.get("overlays", [])):
            ow = f"{onde}, overlay {j}"
            if ov.get("kind") not in OVERLAYS:
                erros.append(f"{ow}: kind `{ov.get('kind')}` inválido ({', '.join(sorted(OVERLAYS))})")
            else:
                for campo in OVERLAY_OBRIGATORIOS[ov["kind"]]:
                    if not ov.get(campo):
                        erros.append(f"{ow}: overlay `{ov['kind']}` precisa de `{campo}`")
            try:
                at = parse_tempo(ov.get("at", 0), palavras, fps)
            except AnchorError as e:
                erros.append(f"{ow}: {e}")
                continue
            if not (t0 - 1e-6 <= at <= t1 + 1e-6):
                erros.append(f"{ow}: `at` {at:.2f}s cai fora do segmento ({t0:.2f}–{t1:.2f}s)")
            if float(ov.get("dur", 0)) <= 0:
                erros.append(f"{ow}: `dur` deve ser > 0")
            if ov.get("kind") == "imagem" and not (p.raiz / str(ov.get("file", ""))).exists():
                erros.append(f"{ow}: arquivo `{ov.get('file')}` não existe")
    for k, sec in enumerate(corte.get("sections") or []):
        onde_s = f"corte.json: seção `{sec.get('title') or f'#{k}'}`"
        if not str(sec.get("title", "")).strip():
            erros.append(f"{onde_s}: sem `title`")
        tr = sec.get("transition", "dissolve")
        if tr not in TRANSICOES_CORTE:
            erros.append(f"{onde_s}: transition `{tr}` inválida ({', '.join(sorted(TRANSICOES_CORTE))})")
        try:
            at = parse_tempo(sec.get("at", 0), palavras, fps)
        except AnchorError as e:
            erros.append(f"{onde_s}: {e}")
            continue
        # a section opens the segment holding its `at`, or the next one to start (so a small
        # negative offset landing in the gap between two segments is fine)
        if faixas and not any(a - 1e-6 <= at <= b + 1e-6 for _, a, b in faixas) \
                and not any(a >= at for _, a, _ in faixas):
            erros.append(f"{onde_s}: `at` {at:.2f}s fica depois do fim do último segmento — "
                         f"não há segmento para esta seção abrir")
    if palavras is None:
        avisos.append("sem transcrição (.estudio/transcricao.json): âncoras `w:` não foram conferidas")
    return erros + _vozes_e_paleta(p), avisos


def validar(p: Projeto) -> tuple[list[str], list[str]]:
    erros, avisos = [], []
    if not p.existe():
        return [f"projeto.json não encontrado em {p.raiz} (rode `estudio.py novo`)"], []
    if p.cfg.get("modo") not in MODOS:
        return [f"projeto.json: modo `{p.cfg.get('modo')}` inválido ({', '.join(sorted(MODOS))})"], []
    if p.modo == "video":
        return validar_video(p)
    imgs = p.imagens()
    if not imgs:
        erros.append("projeto.json: lista `images` vazia")
    for i, im in enumerate(imgs, 1):
        if not im.exists():
            erros.append(f"projeto.json: imagem {i} não existe: {im}")
    for spk, v in p.cfg["voices"].items():
        if "voice" not in v:
            erros.append(f"projeto.json: voz `{spk}` sem campo `voice`")
        if v.get("fx", "narrador") not in FX_VOZ:
            erros.append(f"projeto.json: voz `{spk}` com fx `{v.get('fx')}` desconhecido ({', '.join(sorted(FX_VOZ))})")
    accents = set(p.cfg["palette"]["accents"])
    arte = p.arte()
    crops = arte.get("crops", {})
    # arte.json
    sizes = {}
    for name, c in crops.items():
        where = f"arte.json: recorte `{name}`"
        i = c.get("image")
        if not isinstance(i, int) or not 1 <= i <= len(imgs):
            erros.append(f"{where}: `image` deve ser 1..{len(imgs)}")
            continue
        if i not in sizes and imgs[i - 1].exists():
            from PIL import Image
            sizes[i] = Image.open(imgs[i - 1]).size
        W, H = sizes.get(i, (10**6, 10**6))
        for key in ("box", *(("text", "fill"))):
            rects = [c.get("box")] if key == "box" else c.get(key, [])
            for r in rects:
                if not (isinstance(r, list) and len(r) == 4 and all(isinstance(v, (int, float)) for v in r)):
                    erros.append(f"{where}: `{key}` deve ser [x0, y0, x1, y1]")
                    continue
                x0, y0, x1, y1 = r
                if not (0 <= x0 < x1 <= W and 0 <= y0 < y1 <= H):
                    erros.append(f"{where}: `{key}` {r} fora da imagem {i} ({W}×{H}) ou invertido")
    # scripts
    fmts = p.formatos()
    if not fmts:
        erros.append("nenhum roteiro encontrado (roteiro.json e/ou roteiro_shorts.json)")
    for fmt in fmts:
        try:
            data = p.roteiro(fmt)
        except json.JSONDecodeError as e:
            erros.append(f"{FORMATOS[fmt]['arquivo']}: JSON inválido: {e}")
            continue
        fn = FORMATOS[fmt]["arquivo"]
        ids, line_ids = set(), set()
        for si, sc in enumerate(data.get("scenes", [])):
            sid = sc.get("id", f"#{si}")
            where = f"{fn}: cena `{sid}`"
            if sid in ids:
                erros.append(f"{where}: id repetido")
            ids.add(sid)
            kind = sc.get("kind")
            if kind not in KINDS:
                erros.append(f"{where}: kind `{kind}` inválido ({', '.join(sorted(KINDS))})")
                continue
            if not isinstance(sc.get("image"), int) or not 1 <= sc["image"] <= max(1, len(imgs)):
                erros.append(f"{where}: `image` deve ser 1..{len(imgs)}")
            if sc.get("accent", "red") not in accents:
                erros.append(f"{where}: accent `{sc.get('accent')}` não está na paleta ({', '.join(sorted(accents))})")
            for a in [sc.get("art")] + [l.get("art") for l in sc.get("layers", [])] + [(sc.get("emblem") or {}).get("art")]:
                if a and a not in crops:
                    erros.append(f"{where}: arte `{a}` não existe em arte.json")
            if kind in ("chapter", "panorama") and not sc.get("art") and not sc.get("layers"):
                erros.append(f"{where}: cena `{kind}` precisa de `art` ou `layers`")
            tin = sc.get("transitionIn", {"type": "none"})
            if tin.get("type") not in TRANSICOES:
                erros.append(f"{where}: transitionIn `{tin.get('type')}` inválida ({', '.join(sorted(TRANSICOES))})")
            tout = sc.get("transitionOut")
            if tout and tout.get("type") not in SAIDAS:
                erros.append(f"{where}: transitionOut `{tout.get('type')}` inválida ({', '.join(sorted(SAIDAS))})")
            if sc.get("music", "calm") not in MUSICAS:
                erros.append(f"{where}: music `{sc.get('music')}` inválida ({', '.join(sorted(MUSICAS))})")
            for pt in sc.get("particles", []):
                if pt.get("kind") not in PARTICULAS:
                    erros.append(f"{where}: partícula `{pt.get('kind')}` inválida ({', '.join(sorted(PARTICULAS))})")
            for k in ("preRoll", "postRoll"):
                if not isinstance(sc.get(k, 0), (int, float)):
                    erros.append(f"{where}: `{k}` deve ser número (segundos)")
            lines = sc.get("lines", [])
            if not lines:
                erros.append(f"{where}: sem falas (`lines`)")
            allowed = SCREENS[fmt][kind]
            for ln in lines:
                lw = f"{where}, fala `{ln.get('id')}`"
                if not ln.get("id"):
                    erros.append(f"{where}: fala sem `id`")
                elif ln["id"] in line_ids:
                    erros.append(f"{lw}: id repetido no roteiro")
                line_ids.add(ln.get("id"))
                if ln.get("speaker") not in data["voices"]:
                    erros.append(f"{lw}: speaker `{ln.get('speaker')}` não está em voices ({', '.join(data['voices'])})")
                if not str(ln.get("text", "")).strip():
                    erros.append(f"{lw}: `text` vazio")
                scr = ln.get("screen")
                if scr and not _screen_ok(scr, allowed):
                    erros.append(f"{lw}: screen `{scr}` não existe em `{kind}` ({fmt}); use {', '.join(sorted(allowed))}")
                for s in ln.get("sfx", []):
                    if s.get("name") not in SFX:
                        erros.append(f"{lw}: sfx `{s.get('name')}` inválido ({', '.join(sorted(SFX))})")
                    at = str(s.get("at", "start"))
                    if at not in ("start", "end") and not at.startswith("word:"):
                        erros.append(f"{lw}: sfx.at deve ser start, end ou word:<palavra>")
                    elif at.startswith("word:") and norm(at[5:]) not in [norm(w) for w in ln.get("text", "").split()]:
                        erros.append(f"{lw}: sfx.at `{at}` — palavra não está no texto falado")
                for key in ("hl",):
                    for w in ln.get(key, []):
                        toks = [norm(t) for t in str(ln.get("screenText", ln.get("text", ""))).split()]
                        if norm(w) not in toks:
                            avisos.append(f"{lw}: hl `{w}` não aparece no texto em tela")
                if ln.get("hlFrom") and norm(ln["hlFrom"]) not in [norm(t) for t in str(ln.get("screenText", ln.get("text", ""))).split()]:
                    erros.append(f"{lw}: hlFrom `{ln['hlFrom']}` não aparece no texto em tela")
            # anchors
            for path, at in _walk_at({k: v for k, v in sc.items() if k not in ("lines", "transitionIn", "transitionOut")}):
                base, _, _ = parse_anchor(at)
                if base is None or base in ("start", "end"):
                    continue
                ref, edge, word = split_base(base)
                ln = find_line(lines, ref)
                if ln is None:
                    erros.append(f"{where}: âncora `{at}` em {path} — fala `{ref}` não existe nesta cena")
                elif edge not in ("", "end", "start"):
                    erros.append(f"{where}: âncora `{at}` em {path} — sufixo `.{edge}` inválido (use .end)")
                elif word and norm(word) not in [norm(w) for w in ln.get("text", "").split()]:
                    erros.append(f"{where}: âncora `{at}` em {path} — palavra `{word}` não está na fala")
        tlp = p.timeline_path(fmt)
        if fmt == "shorts" and tlp.exists() and tlp.stat().st_mtime >= p.roteiro_path(fmt).stat().st_mtime:
            dur = json.loads(tlp.read_text()).get("duration", 0)
            if dur > 60:
                avisos.append(f"shorts: {dur:.1f} s na última timeline — o YouTube só trata como Shorts até 60 s")
    return erros, avisos
