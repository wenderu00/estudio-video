"""Transcription of the raw recording (faster-whisper, CPU) and the cut suggestions built from it.

Writes .estudio/transcricao.json (every word with its time and index — the `w:<índice>` anchors of
corte.json point here), .estudio/sugestoes.json (long silences, hesitations, repeated words) and
saida/transcricao.md, the readable version the editor agent works from.

The audio never leaves the machine: the model runs locally.
"""
from __future__ import annotations

import json
import re

import fonte
from ambiente import Ambiente
from projeto import Projeto

MODELO_PADRAO = "medium"
# pt-BR fillers worth flagging (as whole words)
HESITACOES = {"é", "eh", "ahn", "ah", "hum", "hmm", "né", "tipo", "então", "assim", "sabe", "enfim",
              "tipo assim", "quer dizer", "ou seja", "na verdade", "basicamente"}
SILENCIO_MIN = 0.7  # seconds of silence worth suggesting a cut for


def limpo(w: str) -> str:
    return re.sub(r"[^\wÀ-ÿ]", "", str(w).lower())


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:05.2f}"


# -------------------------------------------------------------------- model
def modelo(amb: Ambiente, nome: str):
    from faster_whisper import WhisperModel

    destino = amb.whisper
    destino.mkdir(parents=True, exist_ok=True)
    print(f"· carregando o modelo de transcrição `{nome}` (CPU int8) de {destino} …", flush=True)
    return WhisperModel(nome, device="cpu", compute_type="int8", download_root=str(destino))


# -------------------------------------------------------------------- transcribe
def transcrever(p: Projeto, amb: Ambiente, nome_modelo: str = MODELO_PADRAO, fonte_nome: str | None = None,
                forcar: bool = False) -> dict:
    fonte_nome = fonte_nome or p.fonte_principal()
    _, asr = fonte.extrair_audio(p, fonte_nome, forcar=forcar)
    saida = p.transcricao_path()
    if saida.exists() and not forcar:
        antiga = json.loads(saida.read_text())
        if antiga.get("fonte") == fonte_nome and antiga.get("modelo") == nome_modelo:
            print(f"transcrição em cache: {len(antiga['words'])} palavras ({saida})")
            return antiga
    audio = fonte.ler_wav(asr)
    m = modelo(amb, nome_modelo)
    print(f"· transcrevendo {len(audio) / fonte.SR_ASR / 60:.1f} min de áudio (pode demorar) …", flush=True)
    segs, info = m.transcribe(audio, language="pt", word_timestamps=True, vad_filter=True,
                              vad_parameters={"min_silence_duration_ms": 400},
                              condition_on_previous_text=False, beam_size=5)
    palavras, frases = [], []
    for sg in segs:
        w0 = len(palavras)
        for w in (sg.words or []):
            palavras.append({"i": len(palavras), "w": w.word.strip(), "t": round(w.start, 3),
                             "d": round(max(0.02, w.end - w.start), 3)})
        if len(palavras) == w0:
            continue
        frases.append({"t0": round(sg.start, 3), "t1": round(sg.end, 3), "w0": w0, "w1": len(palavras) - 1,
                       "texto": sg.text.strip()})
        if len(frases) % 25 == 0:
            print(f"  {mmss(sg.end)} · {len(palavras)} palavras", flush=True)
    dados = {"fonte": fonte_nome, "modelo": nome_modelo, "idioma": info.language,
             "dur": round(len(audio) / fonte.SR_ASR, 3), "words": palavras, "frases": frases}
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=1))
    print(f"{len(palavras)} palavras em {len(frases)} frases → {saida}")
    return dados


# -------------------------------------------------------------------- suggestions
def sugerir(p: Projeto, silencio_min: float = SILENCIO_MIN) -> dict:
    """Silences, hesitations and immediate repetitions — candidates for the editor to cut."""
    dados = json.loads(p.transcricao_path().read_text())
    palavras = dados["words"]
    x = fonte.ler_wav(p.work / f"fonte_{dados['fonte']}.wav")
    quietos = [(a, b) for a, b in fonte.silencios(x, fonte.SR, minimo=silencio_min)]

    def palavra_em(t: float) -> int:
        lo, hi = 0, len(palavras)
        while lo < hi:
            mid = (lo + hi) // 2
            if palavras[mid]["t"] < t:
                lo = mid + 1
            else:
                hi = mid
        return min(lo, len(palavras) - 1) if palavras else 0

    sil = [{"t0": a, "t1": b, "dur": round(b - a, 2), "apos": palavra_em(a) - 1, "antes": palavra_em(b)}
           for a, b in quietos]
    hes, rep = [], []
    for i, w in enumerate(palavras):
        t = limpo(w["w"])
        if not t:
            continue
        if t in HESITACOES and w["d"] >= 0.12:
            hes.append({"i": i, "w": w["w"], "t": w["t"]})
        if i and limpo(palavras[i - 1]["w"]) == t and len(t) > 2:
            rep.append({"i": i, "w": w["w"], "t": w["t"]})
    fala = sum(w["d"] for w in palavras)
    out = {"silencios": sil, "hesitacoes": hes, "repeticoes": rep,
           "resumo": {"dur": dados["dur"], "fala": round(fala, 1),
                      "silencio_total": round(sum(s["dur"] for s in sil), 1),
                      "palavras": len(palavras)}}
    p.sugestoes_path().write_text(json.dumps(out, ensure_ascii=False, indent=1))
    r = out["resumo"]
    print(f"{len(sil)} silêncio(s) ≥ {silencio_min}s somando {r['silencio_total']}s · "
          f"{len(hes)} hesitação(ões) · {len(rep)} repetição(ões) → {p.sugestoes_path()}")
    return out


# -------------------------------------------------------------------- markdown
def escrever_md(p: Projeto) -> None:
    """saida/transcricao.md — the working document of the editor agent: timecode, word range and text,
    with the silences and hesitations marked inline."""
    dados = json.loads(p.transcricao_path().read_text())
    sug = json.loads(p.sugestoes_path().read_text()) if p.sugestoes_path().exists() else {}
    palavras, frases = dados["words"], dados["frases"]
    hes = {h["i"] for h in sug.get("hesitacoes", [])}
    rep = {r["i"] for r in sug.get("repeticoes", [])}
    sil_apos = {}
    for s in sug.get("silencios", []):
        sil_apos.setdefault(s["apos"], []).append(s)
    r = sug.get("resumo", {})
    md = [f"# Transcrição — {p.titulo}", "",
          f"Fonte: `{dados['fonte']}` · {mmss(dados['dur'])} · {len(palavras)} palavras"
          + (f" · fala {r.get('fala', 0):.0f}s · silêncio {r.get('silencio_total', 0):.0f}s" if r else ""), "",
          "Cada linha traz o tempo de início, o intervalo de palavras (`w:<índice>`, que serve de âncora em",
          "`corte.json`) e o texto. `⟦…⟧` marca hesitação, `⟪…⟫` repetição imediata e `⏸ Ns` um silêncio.", ""]
    for fr in frases:
        pedacos = []
        for w in palavras[fr["w0"]: fr["w1"] + 1]:
            t = w["w"]
            if w["i"] in hes:
                t = f"⟦{t}⟧"
            elif w["i"] in rep:
                t = f"⟪{t}⟫"
            pedacos.append(t)
            for s in sil_apos.get(w["i"], []):
                pedacos.append(f"⏸{s['dur']:.1f}s")
        md.append(f"- **{mmss(fr['t0'])}** `w:{fr['w0']}–{fr['w1']}` — " + " ".join(pedacos))
    p.saida.mkdir(parents=True, exist_ok=True)
    (p.saida / "transcricao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"transcrição legível: {p.saida / 'transcricao.md'}")


def gerar(p: Projeto, amb: Ambiente, nome_modelo: str = MODELO_PADRAO, forcar: bool = False) -> dict:
    dados = transcrever(p, amb, nome_modelo, forcar=forcar)
    sugerir(p)
    escrever_md(p)
    return dados
