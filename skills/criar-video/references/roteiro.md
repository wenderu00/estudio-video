# Formato do projeto: `projeto.json`, `roteiro.json`, `roteiro_shorts.json`

As chaves são em inglês (o motor lê assim); textos de fala e de tela, em português. Depois de editar
qualquer arquivo, rode `validar` — ele aponta chave errada, âncora que não existe, arte ausente etc.

Exemplo completo e testado: `${CLAUDE_PLUGIN_ROOT}/exemplos/um-vilao-memoravel/` (o vídeo “Um Vilão
Memorável”, 7 imagens → 2:30 + Shorts de 46 s). Copie trechos de lá em vez de inventar formatos.

## Sumário
1. `projeto.json`
2. Estrutura do roteiro e tipos de cena (`kind`)
3. Falas (`lines`) e papéis em tela (`screen`)
4. Âncoras de tempo (`at`)
5. Visual: câmera, camadas, atmosfera, beats, estilo
6. Transições, climas de trilha (`music`) e efeitos sonoros (`sfx`)
7. Duração, ritmo e boas práticas de escrita

## 1. `projeto.json`

```json
{
  "title": "Um Vilão Memorável: o que faria tudo por ela",
  "slug": "um-vilao-memoravel",
  "images": ["1.jpeg", "2.jpeg", "3.jpeg"],
  "voices": {
    "narrador": {"voice": "pt-BR-AntonioNeural", "rate": "-8%", "pitch": "-3Hz", "fx": "narrador", "label": "Narrador"},
    "vilao":    {"voice": "pt-BR-AntonioNeural", "rate": "-16%", "pitch": "-10Hz", "fx": "sombrio", "label": "Vilão"},
    "heroina":  {"voice": "pt-BR-FranciscaNeural", "rate": "+8%", "pitch": "+0Hz", "fx": "sala", "label": "Heroína", "italic": true}
  },
  "palette": {"accents": {"red": {"color": "#E3263A", "text": "#F4EEE6", "fog": "#b8323f"}}},
  "music": {"theme": "padrao", "key": "D", "ambience": "wind", "drone": true, "seed": 2026},
  "mix": {"lufs": -14, "voice_lufs": -15.5, "music_lufs": {"main": -22, "shorts": -20.5}, "ducking_db": 9},
  "render": {"crf": 16, "concurrency": 6, "preset": "slow"}
}
```

- `images`: caminhos relativos ao projeto, **na ordem da história**; as cenas se referem a elas por
  número (`"image": 1` = primeira).
- `voices`: uma entrada por personagem que fala (`speaker` das falas). Vozes pt-BR testadas:
  `pt-BR-AntonioNeural` (masculina, grave), `pt-BR-FranciscaNeural` (feminina),
  `pt-BR-ThalitaMultilingualNeural` (feminina). `rate` e `pitch` no formato do edge-tts
  (`"-8%"`, `"-3Hz"`). `fx`: `narrador` (quente, sala curta) · `sombrio` (camada sussurrada +
  reverb longo e escuro: vilões, entidades) · `sala` (brilhante, sala pequena: outros personagens)
  · `seco` (sem reverb). `italic: true` deixa as falas dessa voz em itálico na tela. Personagens
  diferentes podem usar a mesma voz com `rate`/`pitch` diferentes.
- `palette.accents`: cores de destaque que as cenas usam em `accent` (padrão: `red`, `purple`,
  `blue`). `text` = cor do texto sobre a pincelada dessa cor; `fog` = tom da névoa.
- `music`: `theme` = `"padrao"` (tema de caixinha de música do estúdio) ou `"gerado"` /
  `"gerado:<semente>"` (melodia nova por semente); `key` = tonalidade (`D`, `E`, `C#`…; tudo é
  transposto); `ambience`: `"wind"` ou `"none"`; `drone`: grave contínuo.
- `mix` / `render`: raramente mudam (veja a skill `ajustar-video`).

## 2. Estrutura do roteiro

`roteiro.json` (16:9, 1920×1080) e `roteiro_shorts.json` (9:16, 1080×1920) têm o mesmo formato:
`{"scenes": [ ... ]}`. O Shorts é opcional. Cada cena:

| Campo | Obrigatório | O que é |
|---|---|---|
| `id` | sim | identificador curto (`abertura`, `cap1`…); sem espaços |
| `kind` | sim | `opening`, `chapter`, `panorama`, `moral`, `outro` (tabela abaixo) |
| `image` | sim | número da imagem de fundo (o desfoque dela vira o fundo da cena) |
| `art` ou `layers` | chapter/panorama | recorte(s) de `arte.json` exibidos na cena |
| `accent` | não | cor de destaque (chave da paleta); padrão `red` |
| `number`, `titleLines` | chapter/panorama | selo (`"01"`) e título em linhas de segmentos: `[[{"t": "ELE A "}, {"t": "PERDEU", "hl": true}]]` (`hl` = cor de destaque) |
| `icons` | não | um ícone por tópico: qualquer nome do Lucide (https://lucide.dev/icons, em PascalCase: `HeartCrack`, `Skull`, `Sword`…) ou `HeartTarget`, `Hood` |
| `preRoll`, `postRoll` | não | segundos antes da primeira fala e depois da última (padrão 1.0) |
| `transitionIn` | não | `{"type": "fog", "dur": 1.2}` — como a cena entra (seção 6) |
| `transitionOut` | não | `{"type": "cutBlack", "hold": 0.6}` ou `{"type": "fadeBlack", "dur": 1.2}` |
| `music` | não | clima da trilha na cena (seção 6); padrão `calm` |
| `lines` | sim | falas na ordem (seção 3) |
| `name` | não | nome da cena no `roteiro.md` gerado |

### Tipos de cena (`kind`) e o que aparece em tela

| kind | 16:9 (`roteiro.json`) | 9:16 (`roteiro_shorts.json`) |
|---|---|---|
| `opening` | ganchos (`hook1`, `hook2`…) centralizados; depois cartão de título: `label` (moldura), `title` (entra batendo), `brush` (pintado na cor de destaque). 1–2 camadas de arte (`layers`) | ganchos grandes no topo, um substitui o outro; cartão de título estático em `card` |
| `chapter` | selo + título; `bullet*` (tópicos com ícone, entram com a fala); `statement` (frase solta); `quote` (citação pintada). Arte à direita | arte no topo; selo + título no meio; `caption` (legendas grandes), `quoteLead` + `quote` |
| `panorama` | travelling por uma imagem larga: coluna com título, `intro`, `bullet*` (some no `quoteLead`); `quoteLead` + `quote` no centro; `final` (frase sobre a arte) | igual ao `chapter` do Shorts |
| `moral` | emblema opcional (`emblem`) à esquerda, arte à direita; `line1` (frase pequena) e `line2` (frase grande na cor de destaque — com `hl`/`hlFrom` ela fica branca e só as palavras marcadas ganham a cor); flash quando a `line2` termina | arte no topo, emblema no canto, `line2` (e `line1` opcional) |
| `outro` | `question` (primeira frase grande, resto pintado) e `cta` no formato `"Comente aqui • Inscreva-se"` (antes do • = texto; depois = botão). Depois o texto sobe e libera a área da tela final do YouTube | usa o layout de `moral` |

Uma cena `chapter` pode ter 1–4 tópicos; `quote` e `statement` são opcionais. Falas sem papel em
tela (`screen` vazio) são narradas e legendadas, mas não aparecem como texto animado.

## 3. Falas (`lines`)

```json
{"id": "c1_b3", "speaker": "narrador", "text": "Para ele... não.", "screen": "bullet2",
 "screenText": "Para ele, não.", "pause": 1.4,
 "sfx": [{"name": "hit", "at": "word:não", "offset": 0.0}], "hl": ["não."]}
```

| Campo | O que é |
|---|---|
| `id` | único no roteiro inteiro (`c1_b3`); referência para âncoras |
| `speaker` | chave de `voices` |
| `text` | o que é **falado**. `...` no meio da frase vira uma pausa dramática extra (0,38 s no 16:9) |
| `screen` | papel em tela (tabela da seção 2); vazio = só narração |
| `screenText` | o que aparece escrito, se diferente do falado (sem “...”, com aspas “ ” em citações, caixa alta em títulos) |
| `pause` | silêncio depois da fala, em segundos (0.3–2.4) |
| `ellipsisPause` | substitui a pausa extra dos “...” desta fala |
| `sfx` | efeitos sonoros presos à fala: `at` = `start`, `end` ou `word:<palavra falada>`; `offset` em segundos (negativo = antes); `vel` = volume relativo (padrão 1) |
| `hl` | palavras do `screenText` pintadas na cor de destaque (`["AMA", "DEMAIS."]`) |
| `hlFrom` | pinta a partir desta palavra até o fim (`"nunca"`) |
| `italic` | força itálico (padrão: o da voz) |

## 4. Âncoras de tempo (`at`)

Câmera, entradas de camada, beats e emblema usam `at`, resolvido para quadros da cena:

| Âncora | Significa |
|---|---|
| `"start"`, `"end"` | início / fim da cena |
| `2.5` | 2,5 s depois do início da cena |
| `"c2_q"` | início da fala `c2_q` (`"c2_q.end"` = fim dela) |
| `"c2_q:preço"` | a palavra “preço” sendo dita na fala `c2_q` |
| `"@quote"` | primeira fala da cena com `screen` = `quote` (vale para qualquer papel: `@hook2`, `@bullet2`, `@final`…) |
| `"@quote-8f"`, `"c1_q+0.4"`, `"start+4f"` | deslocamento: `f` = quadros (30 por segundo), sem sufixo ou `s` = segundos |

Prefira âncoras a números: se a narração mudar de duração, a câmera e os efeitos acompanham.

## 5. Visual

**Câmera** (`camera`, na cena ou numa camada): lista de quadros-chave
`{"at": âncora, "s": zoom, "x": foco-x, "y": foco-y}`. `s ≥ 1` cobre a caixa (1.0 = imagem inteira
cabendo; 1.2 = 20% mais perto). `x`/`y` de −1 a 1: −1 alinha a borda esquerda/topo da imagem, +1 a
direita/base; além de ±1 aparece o fundo (use em panorâmicas largas com máscara). A interpolação é
suave. A paralaxe 2.5D acompanha o movimento automaticamente (mapa de profundidade).

```json
"camera": [{"at": "start", "s": 1.04, "x": 0.1, "y": 0.3}, {"at": "end", "s": 1.2, "x": 0.45, "y": -0.5}]
```

Padrões por tipo (quando não há `camera`): `chapter` aproxima devagar; `panorama` atravessa da
esquerda (−1) para a direita (+1); `moral`/`outro`/Shorts aproximam levemente.

**Camadas** (`layers`, principalmente em `opening`): lista de
`{"art", "box": [x, y, largura, altura], "camera", "depth", "glow", "flicker", "saturate", "opacity",
"enter": {"at", "dur", "type": "fade"|"emerge"|"brighten"}, "dim": {"at", "dur", "amount"},
"flare": {"at", "dur", "amount"}}`. `emerge` = sai do escuro e do desfoque; `brighten` = acende
rápido; `dim` = escurece (ex.: quando o título entra); `flare` = brilho que decai. `box` em pixels do
vídeo; sem `box`, o tipo decide (abertura com 2 camadas: esquerda 0–1000 px, direita 900–1920 px).

**Atmosfera**: `"depth": 14` (intensidade da paralaxe em px; 0 desliga), `"glow": {"base": 0.1,
"amp": 0.06, "period": 60}` (brilho pulsante), `"flicker": 0.05` (tremulação de luz de vela/fogo),
`"particles": [{"kind": "embers", "count": 30}, {"kind": "sparks", "count": 16, "color": "150,200,255"}]`
(`embers` brasas, `sparks` faíscas, `ash` cinzas, `dust` poeira, `petals` pétalas; `[]` desliga),
`"fog": {"opacity": 0.14, "color": "#8f6ad8", "speed": 0.5}`, `"backdrop": 0.4` (opacidade do fundo).

**Beats** (`beats`): impactos presos à narração.
`{"at": "c2_q:preço", "shake": true, "flash": {"color": "200,20,40", "peak": 0.3, "dur": 22},
"glow": 0.5, "glowShape": [2, 3, 40, 0]}` — `shake` treme a câmera, `flash` clarão (cor `"r,g,b"` ou
`"#hex"`, padrão a cor de destaque; `cx`/`cy` posicionam), `glow` acende a arte com envelope
`[quadros antes, até o pico, até o fim, nível residual]`.

**Estilo** (`style`, opcional): `chapter`: `fontSize` (56), `iconSize` (74), `quoteSize` (54),
`quoteWidth` (700), `splat` (0–4, forma do respingo do selo), `brush` (0–2, pincelada da citação),
`shakeBullets` (tremer em cada tópico), `shakeAmp`, `bulletGap`; `panorama`: `titleSize`,
`quoteSize`, `quoteWidth`, `splat`, `brush`; `outro`: `artOpacity`, `buttonColor`; Shorts `chapter`:
`shakeCaptions` (`true` ou número de legendas), `quoteUppercase`.

**Outros**: `emblem` (`moral`): `{"art": "mo_sigil", "left": 96, "top": 255, "width": 390, "at": "start+8f"}`
— use um recorte com `"alpha": "luma"` em `arte.json`. `card` (`opening` do Shorts):
`{"label": "UM VILÃO MEMORÁVEL", "title": "O QUE FARIA TUDO", "brush": "POR ELA"}`.
`cta` (`outro`): `{"button": "INSCREVA-SE"}`.

## 6. Transições, trilha e efeitos

**Entrada (`transitionIn.type`)**: `fadeFromBlack` (abertura, recomeço após corte), `crossfade`
(suave), `splatter` (respingo de tinta na cor de destaque: capítulo com impacto), `fog` (névoa:
mistério, magia), `drip` (gotejamento: violência, preço), `slash` (golpe diagonal: conflito,
ação), `whip` (chicote lateral: ritmo rápido, bom no Shorts), `zoomBlur` (zoom com clarão: revelação,
moral), `none`. `dur` típico: 0,9–1,2 s (16:9), 0,35–0,5 s (Shorts). As de sobreposição (`splatter`,
`fog`, `drip`, `slash`, `whip`, `zoomBlur`, `crossfade`) desenham a cena nova por cima da anterior.
**Saída (`transitionOut.type`)**: `cutBlack` (corte seco, com `hold` de preto — a trilha também corta),
`fadeBlack`.

**Climas (`music`)** — cada um ancora acordes nos papéis das falas (título, tópicos, `statement`,
`quote`) e em impactos marcados como `sfx`:

| clima | caráter | como se ancora |
|---|---|---|
| `opening` | caixinha de música com o tema + pad em ré menor | tema começa na 2ª fala |
| `loss` | cordas tristes, fragmento do tema na citação | um acorde por fala; `hit` na última fala antes da citação resolve para lá maior |
| `ritual` | acordes místicos, coro, brilho | tópicos → acordes; `statement` abre; `braam` marca o impacto |
| `price` | tambores acelerando, ostinato, fogo; **corta seco** no fim da citação | tambores do título até a citação |
| `heroes` | cordas + tambor leve; silêncio tenso na última fala | acordes nos tópicos; nota longa sobre a resposta final; piano grave depois |
| `tragedy` | tema completo cuja resolução cai na `quote`; coro; caixinha em `hlFrom` da `final` | `quote` = clímax |
| `moral` | progressão que resolve na `line2`; coro; brilho | última fala = resolução |
| `outro` | tema lento na caixinha, fade final | início da cena |
| `calm` | pads suaves, notas soltas de caixinha | um acorde por fala (genérico) |
| `leve` | **relato pessoal**: pad claro em Fá maior (I–V–vi–IV), caixinha, sem violoncelo | um acorde por fala (genérico) |
| `brisa` | quase só caixinha sobre cordas agudas; o mais discreto | um acorde por fala (genérico) |
| `pulso` | `leve` + pulso de rim shaker, para montagem | um acorde por fala (genérico) |
| `epic` | tambores + coro + cordas | um acorde por fala (genérico) |
| `none` | silêncio de música (só ambiente e efeitos) | — |

**Efeitos (`sfx.name`)**: `boom` (impacto grave: títulos), `hit` (pancada metálica: cada item de
uma lista dura), `braam` (metal grave de trailer: revelação), `bell` (sino: fim de frase marcante),
`splat` (respingo: junto com o selo do capítulo), `brush` (pincelada: antes de citações),
`heartbeat` (coração), `tick` (clique seco: itens rápidos), `rumble` (tremor grave: algo antigo,
enorme), `sword` (espada), `shimmer` (brilho mágico), `swell` (crescendo que explode na palavra),
`whoosh` (passagem de ar). As transições já têm som próprio.

## 7. Duração, ritmo e escrita

- **16:9**: 2–4 min; 5–8 cenas; abertura com gancho de 1–2 frases nos primeiros 5 s; cada capítulo
  12–25 s. **Shorts**: ≤ 55 s de narração (≈ 110–130 palavras), sem `outro`, gancho no 1º segundo,
  `preRoll`/`postRoll` 0,3–0,45 s, pausas 0,2–0,35 s.
- Falas curtas (até ~14 palavras); uma ideia por fala; tópicos de 2–5 palavras.
- `text` é para o ouvido (pode ter “...”); `screenText` é para os olhos (enxuto, sem reticências).
- Siga o texto das imagens quando elas trazem texto — o vídeo deve ser fiel ao material.
- Cada capítulo com uma cor de destaque coerente com a imagem; transições variadas.
