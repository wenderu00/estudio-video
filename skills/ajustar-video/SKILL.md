---
name: ajustar-video
description: Aplica mudanças em um vídeo já produzido com o plugin estudio-video, nos dois modos — voz mais lenta ou grave, música mais baixa, texto errado, tempo de cena, câmera, recorte, cores, transição, efeito sonoro, ou (modo vídeo) corte errado, imagem chapada ou fria, zoom indesejado, legenda ilegível, overlay fora de hora, marca-d'água e tela final — editando projeto.json/roteiro*.json/arte.json/corte.json e refazendo só as etapas necessárias antes do novo render. Use quando o usuário pedir para ajustar, corrigir, mudar ou refazer algo em um vídeo do estúdio (pasta com projeto.json e .estudio/).
---

# Ajustar um vídeo

Motor: `uv run --python 3.12 "${CLAUDE_PLUGIN_ROOT}/motor/estudio.py" --dados "${CLAUDE_PLUGIN_DATA}" <comando> --projeto <PASTA>`
Formato dos arquivos: `${CLAUDE_PLUGIN_ROOT}/skills/criar-video/references/roteiro.md` e `arte.md`
(modo imagens) · `${CLAUDE_PLUGIN_ROOT}/skills/editar-video/references/corte.md` (modo vídeo).

Olhe `projeto.json → modo` antes de tudo: `imagens` usa a primeira tabela, `video` a segunda.

## Modo imagens — o que mudar e o que refazer

Etapas em ordem: `arte` → `narracao` → `timeline` → `trilha` → `mix` → `quadros` → `render` → `qa`.
Refaça a partir da primeira etapa afetada (todas têm cache; só o render é demorado).

| Pedido | Onde mudar | Refazer a partir de |
|---|---|---|
| voz mais lenta/rápida/grave, trocar voz | `projeto.json` → `voices.<fala>.rate` / `pitch` / `voice` | `narracao` |
| texto falado | `text` da fala | `narracao` |
| texto na tela, destaque, título | `screenText`, `hl`, `hlFrom`, `titleLines` | `timeline` (pule trilha/mix) → `quadros` |
| pausas, ritmo, cena longa/curta | `pause`, `preRoll`, `postRoll` | `timeline` |
| transição de entrada | `transitionIn` (muda o tempo das cenas seguintes) | `timeline` |
| câmera, camadas, partículas, névoa, beats, estilo | campos visuais da cena | `timeline` (pule trilha/mix) → `quadros` |
| cores de destaque | `palette` / `accent` | `timeline` (pule trilha/mix) → `quadros` |
| música mais baixa/alta | `mix.music_lufs` (mais negativo = mais baixa; passos de 2 dB) ou `mix.ducking_db` | `mix` |
| volume geral | `mix.lufs` (YouTube normaliza em −14) | `mix` |
| clima da música, tema, tonalidade | `music` da cena, `music.theme`, `music.key` | `trilha` |
| efeito sonoro | `sfx` da fala | `timeline` |
| resto de texto/moldura na imagem, enquadramento do recorte | `arte.json` | `arte --so recortes --previa` (+ `arte --so profundidade` se mudou `box`) |

Depois: `EV validar`, as etapas da tabela, `EV quadros --cenas <ids afetados>` para conferir,
`EV render --formato <main|shorts|ambos>` em segundo plano e `EV qa`. Na dúvida sobre o que foi
afetado, `EV preparar` refaz tudo (rápido com cache).

## Modo vídeo — o que mudar e o que refazer

Etapas em ordem: `montar` → `trilha` → `mix` → `camadas` → `render` → `qa`. (`preparar` faz
`montar` + `trilha` + `mix`; `render` regenera as camadas sozinho quando a timeline é mais nova.)

| Pedido | Onde mudar | Refazer a partir de |
|---|---|---|
| tirar/incluir trecho, mudar ordem, apertar o ritmo | `segments` de `corte.json` | `preparar` |
| corte entrando tarde/cedo demais | `in`/`out` do segmento (folga de 0,1–0,3 s) | `preparar` |
| transição feia entre dois trechos | `transitionIn` do segmento seguinte | `preparar` |
| legenda ilegível, fonte, cor, posição, tamanho | `projeto.json → captions` | `montar` (pule trilha/mix) → `render` |
| legenda com nome próprio/sigla errados | `text` do bloco em `.estudio/timeline-main.json` **não**: corrija em `corte.json` cortando o trecho, ou aceite e edite o `.srt` na entrega | — |
| voz abafada, sibilante, com ronco | `projeto.json → voice.fx` (`gravacao`, `seco`, `sala`) | `mix` |
| música mais baixa/alta, volume geral | `mix.music_lufs`, `mix.ducking_db`, `mix.lufs` | `mix` |
| clima da trilha num trecho, tirar a música | `music` do segmento (`leve`, `brisa`, `pulso`, `none`, …) | `trilha` |
| overlay fora de hora, texto do cartão, b-roll | `overlays` do segmento / segmento com outra `source` | `camadas` → `render` |
| áudio do b-roll atrapalhando | `"mudo": true` ou `gain` no segmento | `preparar` |
| imagem chapada, fria, quente demais, escura | `projeto.json → look` (preset ou números soltos) | `render` (refaz os clipes do corte) |
| correção de cor pronta de fora | `look.lut` apontando para um `.cube` do projeto | `render` |
| zoom indesejado, enquadramento decepado | `camera` do segmento (`{"type":"none"}`) ou `projeto.json → camera` (`auto`, `zoom`) | `montar` → `render` |
| seção sem chip, chip no lugar errado | `sections` de `corte.json` | `preparar` |
| marca-d'água, barra de progresso, tela final | `projeto.json → brand` (`marca`, `progresso`, `tela_final`, `logo`) | `render` (a tela final também pede `montar`) |
| legenda palavra a palavra, caixa alta, fonte própria | `captions.max_words`, `uppercase`, `font_file` | `montar` → `render` |

## Cuidados

- A trilha é gerada por código e depende da duração: qualquer mudança de tempo muda a trilha
  inteira de forma determinística (mesma entrada = mesmo resultado).
- Mudanças só visuais não exigem trilha/mix, mas exigem novo render.
- Shorts precisam continuar ≤ 60 s (`timeline` imprime a duração).
- Modo vídeo: mexer em `in`/`out` muda a duração e, com ela, a trilha inteira — refaça `preparar`,
  não só `montar`. E o `qa` só passa se `quadros = timeline`: se falhar, algum tempo escapou da
  grade de quadros.
- Modo vídeo: os clipes intermediários ficam em `.estudio/work/cortes/` e têm cache por nome; use
  `render --forcar` quando trocar a fonte ou desconfiar do cache.
- Modo vídeo: o nome do clipe carrega um **hash do filtro**, então mexer em `look`, `camera` ou numa
  transição já invalida o clipe certo sozinho — não precisa de `--forcar`, e o que não mudou é
  reaproveitado (refazer só as transições de um corte de 2 min leva segundos).
- Modo vídeo: `.estudio/work/camadas/` guarda um ProRes por trecho com overlay (~0,4 MB por quadro).
  Num vídeo longo e cheio de overlays isso chega a alguns GB — confira o disco antes do render.
