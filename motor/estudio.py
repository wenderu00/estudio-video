# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy", "scipy", "pillow", "opencv-python-headless", "onnxruntime", "edge-tts", "pyloudnorm",
#                 "faster-whisper"]
# ///
"""Estúdio de vídeo — CLI do motor do plugin estudio-video.

Uso: uv run --python 3.12 motor/estudio.py <comando> [--projeto PASTA] [--dados PASTA]

  setup       instala/atualiza o motor (Remotion, Chrome headless, Real-ESRGAN, modelo de profundidade)
  verificar   mostra o estado do ambiente
  novo        cria projeto.json na pasta do projeto (detecta as imagens); --exemplo NOME copia um exemplo;
              --video [ARQUIVO] cria um projeto no modo vídeo (edição de uma gravação bruta)
  status      mostra o que já foi gerado no projeto
  validar     confere projeto.json e os arquivos do modo (roteiro*.json + arte.json, ou corte.json)
  transcrever (modo vídeo) transcreve a fala da gravação e sugere cortes (--modelo, --forcar)
  montar      (modo vídeo) corte.json → timeline, voz editada, legendas .srt e .ass
  camadas     (modo vídeo) renderiza no Remotion os clipes transparentes de overlay/b-roll
  grades      grades de coordenadas sobre as imagens originais (para definir recortes)
  arte        ampliação 4×, recortes/inpaint, profundidade, texturas (--so ETAPA, --previa)
  narracao    narração (edge-tts) de todas as falas, com cache
  timeline    tempos de cena/fala, legendas .srt e saida/roteiro.md
  trilha      trilha sonora e efeitos (stems)
  mix         mixagem e master (-14 LUFS)
  preparar    imagens: validar + arte + narracao + timeline + trilha + mix
              vídeo:   validar + montar + trilha + mix
  quadros     renderiza quadros de revisão e folhas de contato (--formato, --cenas, [quadros…])
  render      render final (imagens: Remotion, --formato main|shorts|ambos; vídeo: ffmpeg)
  qa          confere os mp4 renderizados (specs, loudness, faststart, folhas de contato)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pipeline"))

import ambiente  # noqa: E402
from ambiente import Ambiente  # noqa: E402
from projeto import (DEFAULT_PROJETO, FORMATOS, Projeto, detectar_imagens, musica_do_slug, slugify,  # noqa: E402
                     validar)

EXEMPLOS = Path(__file__).resolve().parent.parent / "exemplos"


def fmts_arg(p: Projeto, fmt: str | None) -> list[str]:
    disp = p.formatos()
    if fmt in (None, "ambos", "todos"):
        return disp
    if fmt not in disp:
        raise SystemExit(f"formato `{fmt}` não tem roteiro neste projeto (disponíveis: {', '.join(disp) or 'nenhum'})")
    return [fmt]


def cmd_setup(a, amb: Ambiente):
    amb.dados.mkdir(parents=True, exist_ok=True)
    print(f"diretório de dados: {amb.dados}")
    nv = ambiente.versao_node()
    if not nv or nv[0] < 18:
        raise SystemExit("Node.js ≥ 18 é necessário (https://nodejs.org). Instale e rode o setup de novo.")
    amb.sincronizar(forcar=a.forcar)
    if a.forcar or not amb.npm_ok():
        amb.instalar_npm()
    amb.garantir_navegador()
    try:
        ambiente.ffmpeg_origem()
    except RuntimeError:
        amb.instalar_ffmpeg_estatico()
        ambiente.usar(amb)
    amb.instalar_tipografias()
    if not a.sem_ia:
        amb.instalar_realesrgan()
        ok, det = amb.testar_realesrgan()
        print(f"· Real-ESRGAN: {'ok' if ok else 'indisponível'} ({det}){'' if ok else ' — a ampliação usará Lanczos'}")
        amb.instalar_profundidade()
        amb.instalar_rosto()
    cmd_verificar(a, amb)


def cmd_verificar(a, amb: Ambiente):
    ok_all = True
    for item, ok, det in ambiente.verificar(amb):
        print(f"  {'✓' if ok else '✗'} {item:26s} {det}")
        ok_all &= ok or item in ("Real-ESRGAN", "modelo de profundidade", "modelo de transcrição",
                                 "detector de rosto", "fontes das legendas",
                                 "ffmpeg: x264/aac/legendas", "disco livre ≥ 3 GB")
    print("pronto" if ok_all else "faltam itens: rode `estudio.py setup`")
    return ok_all


FPS_PADRAO = [24, 25, 30, 50, 60]


def cmd_novo_video(a, amb, raiz: Path):
    """Video mode: the project's input is a raw recording, not a list of images."""
    import fonte
    arq = raiz / "projeto.json"
    if a.video == "auto":
        achados = fonte.detectar_videos(raiz)
        if not achados:
            raise SystemExit(f"nenhum vídeo encontrado em {raiz} (formatos: {', '.join(sorted(fonte.VID_EXT))})")
        rel = achados[0]
        if len(achados) > 1:
            print(f"vídeos na pasta: {', '.join(achados)} — usando o maior ({rel})")
    else:
        src = Path(a.video).expanduser()
        if not src.is_absolute():
            src = (raiz / src).resolve()
        if not src.exists():
            raise SystemExit(f"vídeo não encontrado: {src}")
        rel = str(src.relative_to(raiz)) if src.is_relative_to(raiz) else str(src)
    if arq.exists() and not a.forcar:
        raise SystemExit(f"projeto.json já existe em {raiz} (use --forcar para recriar)")
    info = fonte.info(raiz / rel)
    fps = min(FPS_PADRAO, key=lambda v: abs(v - info["fps"]))
    if abs(fps - info["fps"]) > 1.5:
        fps = 30
    titulo = a.titulo or raiz.name.replace("-", " ").replace("_", " ").title()
    slug = a.slug or slugify(titulo)
    cfg = {
        "title": titulo,
        "slug": slug,
        "modo": "video",
        "sources": {"principal": rel},
        "voice": DEFAULT_PROJETO["voice"],
        "captions": DEFAULT_PROJETO["captions"],
        "look": DEFAULT_PROJETO["look"],
        "camera": DEFAULT_PROJETO["camera"],
        "brand": DEFAULT_PROJETO["brand"],
        "music": {**musica_do_slug(slug), "drone": False},
        "render": {**DEFAULT_PROJETO["render"], "fps": fps, "width": info["width"], "height": info["height"]},
    }
    arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    gi = raiz / ".gitignore"
    linhas = gi.read_text().splitlines() if gi.exists() else []
    if ".estudio/" not in linhas:
        gi.write_text("\n".join(linhas + [".estudio/"]) + "\n")
    p = Projeto(raiz)
    fonte.descrever(p)
    if not info["audio"]:
        print("⚠ a gravação não tem faixa de áudio — o corte por transcrição não vai funcionar")
    print(f"criado {arq}")
    print(f"  fonte    {rel} · {info['width']}×{info['height']} · {info['fps']:g} fps · "
          f"{int(info['dur'] // 60)}:{info['dur'] % 60:04.1f} · {info['tamanho_mb']} MB")
    print(f"  saída    {info['width']}×{info['height']} @ {fps} fps (CFR)")
    print(f"projeto: {p.titulo} (slug {p.slug}) · build em {p.build} · saída em {p.saida}")
    print("próximo passo: `transcrever`")


def cmd_novo(a, amb):
    raiz = Path(a.projeto).expanduser().resolve()
    raiz.mkdir(parents=True, exist_ok=True)
    if a.video:
        return cmd_novo_video(a, amb, raiz)
    arq = raiz / "projeto.json"
    if a.exemplo:
        ex = EXEMPLOS / a.exemplo
        if not ex.is_dir():
            raise SystemExit(f"exemplo `{a.exemplo}` não existe ({', '.join(p.name for p in EXEMPLOS.iterdir())})")
        for f in ("roteiro.json", "roteiro_shorts.json", "arte.json"):
            if (ex / f).exists() and not (raiz / f).exists():
                shutil.copy2(ex / f, raiz / f)
                print(f"copiado {f}")
        base = json.loads((ex / "projeto.json").read_text())
    else:
        base = {}
    if arq.exists() and not a.forcar:
        print(f"projeto.json já existe em {raiz} (use --forcar para recriar)")
    else:
        imgs = detectar_imagens(raiz)
        if base.get("images") and all((raiz / i).exists() for i in base["images"]):
            imgs = base["images"]
        titulo = a.titulo or base.get("title") or raiz.name.replace("-", " ").replace("_", " ").title()
        slug = a.slug or base.get("slug") or slugify(titulo)
        # O exemplo manda no arranjo (theme/ambience/drone), mas tonalidade e semente são
        # derivadas do slug: os exemplos carregam os valores de fábrica, e herdá-los faria
        # todo projeto criado a partir de um exemplo cair de novo na mesma trilha.
        musica = {**musica_do_slug(slug), **(base.get("music") or {})}
        for campo in ("key", "seed"):
            if musica[campo] == DEFAULT_PROJETO["music"][campo]:
                musica[campo] = musica_do_slug(slug)[campo]
        cfg = {
            "title": titulo,
            "slug": slug,
            "images": imgs,
            "voices": base.get("voices", DEFAULT_PROJETO["voices"]),
            "music": musica,
        }
        for k in ("palette", "mix", "render"):
            if k in base:
                cfg[k] = base[k]
        arq.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
        print(f"criado {arq} — {len(imgs)} imagem(ns): {', '.join(imgs[:12])}{' …' if len(imgs) > 12 else ''}")
    gi = raiz / ".gitignore"
    linhas = gi.read_text().splitlines() if gi.exists() else []
    if ".estudio/" not in linhas:
        gi.write_text("\n".join(linhas + [".estudio/"]) + "\n")
    p = Projeto(raiz)
    if ambiente.ffmpeg_origem()[1].startswith("flatpak") and not str(raiz).startswith(str(Path.home())):
        print("⚠ o ffmpeg vem do flatpak, que só enxerga a pasta pessoal: mova o projeto para dentro de ~")
    print(f"projeto: {p.titulo} (slug {p.slug}) · build em {p.build} · saída em {p.saida}")


def cmd_status(a, amb):
    p = Projeto(Path(a.projeto))
    def st(path, label):
        n = len(list(path.glob("*"))) if path.is_dir() else None
        ok = path.exists() and (n is None or n > 0)
        print(f"  {'✓' if ok else '·'} {label:28s} {path.relative_to(p.raiz) if path.is_relative_to(p.raiz) else path}" + (f" ({n})" if n else ""))
    print(f"projeto {p.titulo} ({p.slug}) em {p.raiz} · modo {p.modo}")
    st(p.arquivo, "projeto.json")
    if p.modo == "video":
        for nome, rel in p.sources().items():
            st(p.raiz / rel, f"fonte {nome}")
        st(p.transcricao_path(), "transcrição")
        st(p.sugestoes_path(), "sugestões de corte")
        st(p.corte_path(), "corte.json")
        st(p.timeline_path("main"), "timeline main")
        st(p.work / "voz-main.wav", "voz editada")
        st(p.work / "stems_main", "trilha main")
        st(p.audio / "mix-main.wav", "mix main")
        st(p.work / "master.mp4", "master (cortes)")
        st(p.mp4("main"), "vídeo final")
        return
    for f in FORMATOS:
        st(p.roteiro_path(f), f"roteiro {f}")
    st(p.raiz / "arte.json", "arte.json")
    st(p.up, "imagens ampliadas")
    st(p.art / "art.json", "recortes")
    st(p.tts, "narração (cache)")
    for f in p.formatos():
        st(p.timeline_path(f), f"timeline {f}")
        st(p.work / f"stems_{f}", f"trilha {f}")
        st(p.audio / f"mix-{f}.wav", f"mix {f}")
        st(p.mp4(f), f"vídeo {f}")


def cmd_validar(a, amb) -> bool:
    p = Projeto(Path(a.projeto))
    erros, avisos = validar(p)
    for e in erros:
        print(f"  ✗ {e}")
    for w in avisos:
        print(f"  ! {w}")
    print("válido" if not erros else f"{len(erros)} erro(s)")
    return not erros


def cmd_transcrever(a, amb):
    import transcricao
    p = Projeto(Path(a.projeto))
    if p.modo != "video":
        raise SystemExit("`transcrever` só existe no modo vídeo (projeto.json com \"modo\": \"video\")")
    transcricao.gerar(p, amb, a.modelo or transcricao.MODELO_PADRAO, forcar=a.forcar)


def cmd_montar(a, amb):
    import corte
    p = Projeto(Path(a.projeto))
    if p.modo != "video":
        raise SystemExit("`montar` só existe no modo vídeo; no modo imagens use `timeline`")
    if not cmd_validar(a, amb):
        raise SystemExit("corrija os erros antes de montar")
    corte.gerar(p, amb)


def cmd_camadas(a, amb):
    import remotion
    p = Projeto(Path(a.projeto))
    if p.modo != "video":
        raise SystemExit("`camadas` só existe no modo vídeo")
    remotion.camadas(p, amb, json.loads(p.timeline_path("main").read_text()))


def cmd_grades(a, amb):
    import arte
    arte.grades(Projeto(Path(a.projeto)))


def cmd_arte(a, amb):
    import arte
    p = Projeto(Path(a.projeto))
    so = a.so
    if so in (None, "ampliar"):
        arte.ampliar(p, amb, forcar=a.forcar)
    if so in (None, "recortes"):
        arte.recortes(p)
    if so in (None, "profundidade"):
        arte.profundidade(p, amb, forcar=a.forcar)
    if so in (None, "texturas"):
        arte.texturas(p, forcar=a.forcar)
    if a.previa or so == "previa":
        arte.previa(p)


def cmd_narracao(a, amb):
    import narracao
    narracao.gerar(Projeto(Path(a.projeto)))


def cmd_timeline(a, amb):
    import timeline
    timeline.gerar(Projeto(Path(a.projeto)))


def cmd_trilha(a, amb):
    import trilha
    p = Projeto(Path(a.projeto))
    trilha.gerar(p, fmts_arg(p, a.formato))


def cmd_mix(a, amb):
    import mix
    p = Projeto(Path(a.projeto))
    mix.gerar(p, fmts_arg(p, a.formato))


def cmd_preparar(a, amb):
    if not cmd_validar(a, amb):
        raise SystemExit("corrija os erros de validação antes de preparar")
    p = Projeto(Path(a.projeto))
    if p.modo == "video":
        import corte
        corte.gerar(p, amb)
        a.formato = None
        cmd_trilha(a, amb)
        cmd_mix(a, amb)
        print("pronto para `quadros` e `render`")
        return
    a.so, a.previa = None, False
    cmd_arte(a, amb)
    cmd_narracao(a, amb)
    cmd_timeline(a, amb)
    a.formato = None
    cmd_trilha(a, amb)
    cmd_mix(a, amb)
    print("pronto para `quadros` e `render`")


def cmd_quadros(a, amb):
    import remotion
    p = Projeto(Path(a.projeto))
    cenas = set(a.cenas.split(",")) if a.cenas else None
    if p.modo == "video":
        import montagem
        tl = json.loads(p.timeline_path("main").read_text())
        sel = [(int(f), "") for f in a.frames] if a.frames else montagem.quadros_auto(tl, cenas)
        montagem.quadros(p, [f for f, _ in sel], {f: lab for f, lab in sel})
        return
    for fmt in fmts_arg(p, a.formato):
        tl = json.loads(p.timeline_path(fmt).read_text())
        if a.frames:
            sel = [(int(f), "") for f in a.frames]
        else:
            sel = remotion.quadros_auto(tl, cenas)
        remotion.stills(p, amb, fmt, [f for f, _ in sel], {f: lab for f, lab in sel})


def cmd_render(a, amb):
    import remotion
    p = Projeto(Path(a.projeto))
    if p.modo == "video":
        import montagem
        montagem.render(p, amb, forcar=a.forcar)
        return
    for fmt in fmts_arg(p, a.formato):
        print(remotion.render(p, amb, fmt))


def cmd_qa(a, amb):
    import qa
    p = Projeto(Path(a.projeto))
    ok = True
    for fmt in fmts_arg(p, a.formato):
        r = qa.conferir(p, fmt, every=a.intervalo or (4.0 if fmt == "main" else 2.0))
        ok &= all(r["checks"].values())
    if not ok:
        raise SystemExit(1)


def main():
    ap = argparse.ArgumentParser(prog="estudio.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", choices=["setup", "verificar", "novo", "status", "validar", "transcrever", "grades",
                                        "montar", "camadas", "arte", "narracao", "timeline", "trilha", "mix", "preparar", "quadros",
                                        "render", "qa"])
    ap.add_argument("frames", nargs="*", help="quadros específicos (comando quadros)")
    ap.add_argument("--projeto", default=".", help="pasta do projeto (padrão: pasta atual)")
    ap.add_argument("--dados", default=None, help="diretório de dados do motor (padrão: ESTUDIO_DADOS ou o do plugin)")
    ap.add_argument("--formato", choices=["main", "shorts", "ambos"], default=None)
    ap.add_argument("--so", choices=["ampliar", "recortes", "profundidade", "texturas", "previa"], default=None)
    ap.add_argument("--previa", action="store_true", help="arte: gera a folha de prévia dos recortes")
    ap.add_argument("--cenas", default=None, help="quadros: só estas cenas (ids separados por vírgula)")
    ap.add_argument("--intervalo", type=float, default=None, help="qa: segundos entre quadros das folhas")
    ap.add_argument("--titulo", default=None)
    ap.add_argument("--slug", default=None)
    ap.add_argument("--exemplo", default=None, help="novo: copia roteiros e arte de exemplos/<NOME>")
    ap.add_argument("--video", nargs="?", const="auto", default=None,
                    help="novo: cria um projeto no modo vídeo a partir da gravação (sem valor, detecta na pasta)")
    ap.add_argument("--modelo", default=None, help="transcrever: modelo do faster-whisper (padrão medium)")
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--sem-ia", action="store_true", help="setup: não baixa Real-ESRGAN nem o modelo de profundidade")
    a = ap.parse_args()
    amb = Ambiente(Path(a.dados) if a.dados else None)
    ambiente.usar(amb)
    r = globals()[f"cmd_{a.comando}"](a, amb)
    if a.comando == "validar" and r is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
