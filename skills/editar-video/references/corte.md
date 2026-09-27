# `corte.json` — a lista de cortes do modo vídeo

É o arquivo equivalente ao `roteiro.json` do modo imagens: diz **quais trechos da gravação ficam**,
em que ordem, com que transição, como a câmera se move dentro deles e o que aparece por cima. Tudo
o mais (legenda, trilha, mixagem) sai daqui. O **acabamento de imagem** e a **marca** não ficam
aqui: moram em `projeto.json` (seções “Acabamento” e “Marca”, no fim deste documento).

```jsonc
{
  "sections": [
    {"at": "w:120", "n": "02", "title": "O problema", "transition": "crossfade"}
  ],
  "segments": [
    {
      "id": "s1",                       // único, curto; vira o id da cena na timeline
      "in": "w:2-0.15",                 // início na FONTE
      "out": "w:12.end+0.25",           // fim na FONTE (exclusivo)
      "note": "abre direto na ideia",   // opcional, só para leitura humana
      "source": "principal",            // opcional; outra fonte de projeto.json (b-roll)
      "mudo": false,                    // opcional; descarta o áudio deste trecho
      "gain": 1.0,                      // opcional; ganho linear do áudio do trecho
      "music": "calm",                  // clima da trilha (ver abaixo)
      "camera": {"type": "punch", "to": 1.08},   // movimento dentro do trecho
      "look": {"preset": "cinema"},              // acabamento só deste trecho
      "transitionIn":  { "type": "fadeFromBlack", "dur": 0.5 },
      "transitionOut": { "type": "fadeToBlack", "dur": 0.8 },
      "overlays": [ { "kind": "cartao", "at": "w:31", "dur": 3.0, "title": "A regra" } ]
    }
  ]
}
```

## Tempos e âncoras

`in`, `out`, `at` e `camera.at` aceitam três formas, todas com um deslocamento opcional `±<n>` em
segundos (ou `±<n>f` em quadros):

| Forma | Exemplo | Significa |
|---|---|---|
| segundos | `12.5`, `12.5+0.2` | 12,5 s na fonte |
| timecode | `0:12.480`, `1:02:03.5` | M:SS.mmm (ou H:MM:SS.mmm) |
| palavra | `w:1840`, `w:1840.end`, `w:1840-0.15` | início (ou fim) da palavra 1840 da transcrição |

Os índices `w:` são os que aparecem em `saida/transcricao.md` (`w:<início>–<fim>` em cada linha).
**Prefira âncoras de palavra**: elas sobrevivem a uma nova transcrição e dizem o que você quis dizer.
Dê sempre uma folga: `w:N-0.15` antes da primeira palavra e `w:M.end+0.25` depois da última, senão o
corte come a respiração e o começo da consoante.

Todo tempo é arredondado para a grade de quadros antes de qualquer coisa — o corte do vídeo e a
fatia do áudio usam exatamente o mesmo limite.

## Seções (`sections`)

Marcam onde cada assunto começa. Cada seção rende **duas coisas de graça**: a transição de entrada
do segmento que ela abre e um chip numerado (`01 · O problema`) no canto.

| Campo | O que é |
|---|---|
| `at` | onde o assunto começa, na fonte (mesma gramática acima) |
| `n` | número do capítulo (`"01"`); opcional |
| `title` | nome do assunto — obrigatório |
| `transition` | transição de entrada (padrão `crossfade`); veja a tabela abaixo |
| `dur`, `dur_transicao` | tempo do chip na tela (2,6 s) e da transição (0,25 s) |
| `accent`, `position` | cor da paleta e `left`/`right` |

Uma seção cujo `at` cai **no começo de um segmento** (até 1,2 s de distância) abre aquele segmento.
Uma que cai **no meio** de um segmento só coloca o chip ali — dar transição a ela significaria
cortar o segmento em dois, e isso é decisão do corte, não da seção. A transição só entra se o
segmento ainda não tiver escolhido uma.

## Transições

**Entrada (`transitionIn.type`)**. `corte`/`none` é o padrão e não consome nada. Todas as outras
**sobrepõem** este segmento ao anterior por `dur`, encurtando o vídeo final — e por isso o primeiro
segmento não pode usá-las (use `fadeFromBlack`).

| tipo | efeito | quando usar |
|---|---|---|
| `corte` / `none` | corte seco | padrão, dentro de um assunto |
| `fadeFromBlack` | vem do preto | abertura, recomeço |
| `crossfade` / `dissolve` | dissolvência | salto feio de enquadramento, troca de assunto |
| `blur` | passa por um borrão | passagem suave |
| `whipLeft` / `whipRight` | chicote lateral com borrão de movimento | ritmo, energia |
| `zoomPunch` | o plano que sai avança e o que entra assenta | ênfase |
| `sliceH` / `sliceV` | fatias deslizando | moderno, seco |
| `wipeDiagonal` | varredura diagonal | novo assunto |
| `radial` / `circleOpen` | varredura circular | abre um tema |
| `pixel` | pixelização | assunto técnico |
| `dipBlack` / `dipWhite` | passa pelo preto / branco | passagem de tempo |
| `glitch` | rasgo em faixas + separação de canais | erro, bug, “quebrou” |
| `filmBurn` | estouro branco com grão | fim de capítulo |
| `hazard` | varredura em faixas diagonais | alerta |
| `granulado` | dissolvência pontilhada do ffmpeg | textura de vídeo antigo |

> **Cuidado com o material.** Entre dois planos quase idênticos (a mesma pessoa, na mesma cadeira,
> na mesma parede) uma varredura geométrica é **invisível** — o espectador não vê diferença para um
> corte seco. Guarde `wipeDiagonal`, `radial`, `sliceH` e companhia para quando a imagem muda de
> verdade (entra b-roll, entra tela cheia). Em cabeça falante, o que se nota é `crossfade`,
> `whipLeft/Right`, `zoomPunch`, `dipBlack` e `glitch`.

**Saída (`transitionOut.type`)**: `fadeToBlack`, `fadeToWhite`, `dipToColor` (exige `color`
`#RRGGBB`). Sempre com `dur` > 0. As transições não podem consumir o segmento inteiro.

## Câmera (`camera`)

Um recorte animado dentro do trecho — não altera a contagem de quadros nem a sincronia.

```jsonc
"camera": {"type": "punch", "from": 1.0, "to": 1.08, "focus": [0.5, 0.42]}
```

| `type` | O que faz |
|---|---|
| `none` | parado |
| `punch` | aproxima devagar (de `from` a `to`) |
| `pull` | afasta |
| `hold` | recorte fixo — reenquadrar, ex.: mais fechado no rosto |
| `snap` | salta de `from` para `to` num instante (`at`) — o zoom de impacto |

`from`/`to` são zoom (1.0 = quadro inteiro, 3.0 no máximo). `focus` é `[x, y]` de 0 a 1: o ponto que
fica no centro; sem ele, o motor usa o rosto que detectou, ou o centro.

**Padrão do motor:** todo segmento com mais de 6 s **em que há um rosto na tela** ganha um movimento
suave de 6%, alternando `punch` e `pull` entre um segmento e o seguinte. Sem rosto (captura de tela,
diagrama, b-roll) a câmera fica parada de propósito — aproximar cortaria texto. Para desligar ou
ajustar: `projeto.json → camera` (`auto`, `zoom`, `dur_minima`). Para desligar num trecho só:
`"camera": {"type": "none"}`.

## Overlays

Desenhados pelo Remotion e compostos por cima do corte. `at` é o tempo **na fonte** (mesma gramática
acima), dentro do segmento; `dur` é em segundos. Todos aceitam `accent` (chave da paleta ou um
`#RRGGBB`) e, quando faz sentido, `position`.

| `kind` | Campos | Para quê |
|---|---|---|
| `titulo` | `title`, `sub?` | cartela grande no centro |
| `cartao` | `title`, `sub?`, `position?` | lower third de um conceito |
| `secao` | `title`, `n?` | chip numerado (o normal é vir de `sections`) |
| `tarja` | `name`, `role?` | apresentação de quem fala |
| `callout` | `title`, `sub?`, `icon?` | nota flutuante com ícone (qualquer nome do [Lucide](https://lucide.dev/icons), em PascalCase) |
| `card` | `title`, `items[]`, `position?` | lista/definição que entra linha a linha |
| `destaque` | `box` `[x, y, w, h]` em 0..1, `title?` | cantoneiras + escurece o resto do quadro |
| `imagem` | `file` (relativo à pasta do projeto), `box?` | imagem por cima, com movimento lento (tela cheia com `box` `[0,0,1,1]`) |
| `vinheta` | `title?`, `sub?` | abertura curta com a marca |
| `telaFinal` | `title?`, `sub?`, `cta?` | encerramento; deixa a direita livre para os cards do YouTube |

Só os intervalos com overlay passam pelo Chrome do Remotion — por isso overlay é barato, e o resto
do vídeo nunca é recomprimido duas vezes por causa deles. Em troca, cada trecho com overlay vira um
clipe **ProRes 4444** em `.estudio/work/camadas/`, que ocupa cerca de **0,4 MB por quadro**: mil
quadros de overlay são ~400 MB de cache temporário. É cache, some com `.estudio/`.

**Marca-d'água e barra de progresso não são overlays** — duram o vídeo inteiro, e um overlay de
vídeo inteiro empurraria cada quadro pelo navegador. Estão em `projeto.json → brand` e são feitas
pelo ffmpeg, de graça.

## B-roll

B-roll de tela cheia é **um segmento com outra `source`** (registre o arquivo em
`projeto.json → sources`), normalmente com `"mudo": true`. B-roll por cima da fala é um overlay
`imagem`.

## Acabamento da imagem — `projeto.json → look`

Aplicado a cada clipe do corte, antes das transições (cada plano entra na mistura já tratado).

```jsonc
"look": { "preset": "natural", "lut": null, "vignette": 0.26, "grain": 2.0 }
```

| `preset` | Caráter |
|---|---|
| `natural` | **padrão**: contraste e saturação leves, quente discreto, vinheta e grão sutis |
| `limpo` | só nitidez |
| `quente` / `frio` | mesma base, puxando para âmbar ou para azul |
| `cinema` | curva mais dura, leve dessaturação, vinheta forte, grão e bloom |
| `nenhum` | imagem crua (o que o motor fazia antes) |

O preset preenche os números; qualquer campo escrito à mão vence:
`contrast`, `saturation`, `brightness`, `gamma`, `temp` (−100 a 100, **positivo = mais quente**),
`vignette` (0–1), `grain` (0–40), `sharpen` (0–3), `bloom` (0–1), `chroma` (aberração, 0–20).

`lut` é o caminho de um `.cube` relativo à pasta do projeto e tem precedência sobre os números — a
porta para uma correção de cor feita fora. Um segmento pode ter o seu próprio `look`; declarar
`preset` nele recomeça os números a partir daquele preset.

> Mudar o `look` invalida os clipes intermediários (o nome deles carrega um hash do filtro), então
> o próximo `render` refaz o corte. É rápido, e é o que garante que a mudança apareça de verdade.

## Marca — `projeto.json → brand`

```jsonc
"brand": {"logo": "assets/logo.png", "name": "Canal", "handle": "@canal", "color": "#E3263A",
          "marca": true, "marca_opacidade": 0.55, "marca_altura": 0.06,
          "progresso": true, "tela_final": 8.0}
```

- `logo` + `marca`: marca-d'água no canto superior direito o vídeo inteiro (ffmpeg, sem custo).
- `progresso`: barra fina na base mostrando o avanço (ffmpeg).
- `tela_final`: segundos de `telaFinal` no fim do vídeo; `0` desliga.
- `color`: cor da marca; serve de `accent` para a vinheta e a tela final.

## Legendas — `projeto.json → captions`

Não ficam em `corte.json`: o texto sai da transcrição, recortado em blocos.

| Campo | Efeito |
|---|---|
| `font`, `size`, `bold` | fonte instalada no sistema, corpo em pixels da altura de saída |
| `font_file` | **padrão `Barlow-Bold.ttf`**, uma das fontes que vêm com o plugin (`Anton-Regular.ttf`, `ArchivoBlack-Regular.ttf`); ou um caminho de `.ttf` dentro do projeto. Não depende do que está instalado na máquina |
| `color`, `highlight` | cor do texto e da palavra falada no momento |
| `outline`, `shadow`, `box`, `bg_opacity` | contorno, sombra, caixa sólida atrás e opacidade dela |
| `position`, `margin`, `safe_bottom` | `bottom`/`center`/`top`, margem e folga extra na base |
| `karaoke` | `true` pinta a palavra corrente; `false` mostra o bloco inteiro liso |
| `pop`, `fade` | entrada com leve escala e fade em ms — aplicados ao **bloco**, não a cada palavra |
| `uppercase` | tudo em caixa alta |
| `capitalizar` | maiúscula na primeira palavra de cada segmento |
| `max_chars`, `max_lines` | tamanho do bloco de legenda |
| `max_words` | `> 0` troca o bloco por N palavras por vez (legenda grande, estilo Shorts) |

## Trilha (`music`)

Duas famílias, e a escolha entre elas importa mais que o clima exato.

**Relato pessoal — Fá maior, sem violoncelo.** Escritos para alguém falando de si (aula, vlog,
depoimento). É daqui que você deve escolher em vídeo falado:

| clima | caráter |
|---|---|
| `leve` | **o padrão para relato**: pad claro em I–V–vi–IV, caixinha nas viradas, sem percussão nem coro |
| `brisa` | quase só caixinha sobre um véu de cordas agudas — deixa a fala respirar; bom para fechar |
| `pulso` | `leve` com um pulso de rim shaker: movimento para montagem, sem peso de tambor |
| `none` | sem música |

**Narrativa dramática — ré menor, cordas graves e violoncelo.** `calm`, `opening`, `loss`,
`ritual`, `price`, `heroes`, `tragedy`, `moral`, `outro`, `epic`. Vêm do modo imagens e foram
escritos para contar a história de outra pessoa.

> **`calm` não é neutro.** Apesar do nome, ele toca supersaw escuro filtrado em 1000 Hz **mais
> violoncelo**, em ré menor — vocabulário de cinema, que soa pesado sob um relato pessoal mesmo sem
> tambor nenhum. Para conteúdo falado prefira `leve`. E `heroes` (tambor) e `moral` (coro) são
> dramáticos de verdade: em relato pessoal soam como trailer.
