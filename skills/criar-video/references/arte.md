# Recortes: `arte.json`

Cada imagem do projeto é ampliada 4× (Real-ESRGAN; sem GPU, Lanczos) e dela saem **recortes**: as
ilustrações sem o texto que foi desenhado por cima. As cenas usam os recortes pelo nome (`art`,
`layers[].art`, `emblem.art`).

```json
{
  "scale": 4,
  "crops": {
    "c1_art":   {"image": 2, "box": [200, 6, 497, 340], "text": [[200, 10, 335, 72]], "fill": [[30, 248, 256, 338]]},
    "c5_pan":   {"image": 6, "box": [285, 13, 1003, 299], "text": [[535, 236, 785, 290]]},
    "mo_sigil": {"image": 7, "box": [20, 5, 185, 215], "alpha": "luma"}
  }
}
```

| Campo | O que é |
|---|---|
| nome da chave | nome do recorte (`c1_art`, `op_villain`…): minúsculas, sem espaço |
| `image` | número da imagem em `projeto.json` → `images` |
| `box` | `[x0, y0, x1, y1]` em **pixels da imagem original** (não da ampliada): a região da ilustração |
| `text` | retângulos com **letras** sobre a arte: o motor detecta só os pixels das letras e reconstrói o fundo (inpaint) |
| `fill` | retângulos **sólidos** (caixas de citação, faixas, selos) apagados por inteiro |
| `alpha` | `"luma"`: emblema claro sobre fundo escuro vira PNG com transparência (use em `emblem`) |
| `depth` | `false` desliga o mapa de profundidade deste recorte (padrão: ligado, exceto `alpha`) |

## Como escolher as caixas

1. Rode `grades`: gera `.estudio/grades/grade_<n>.jpg` — cada imagem original ampliada para leitura,
   com linhas a cada 10 px (fracas) e 50 px (numeradas: amarelo = x no topo, ciano = y à esquerda).
   Leia as coordenadas direto da grade.
2. A caixa (`box`) deve ficar **dentro** das molduras/linhas decorativas do card, sem pegar bordas
   (elas aparecem quando a câmera chega perto da borda). Na dúvida, 3–6 px para dentro.
3. Tudo que for texto, selo, número ou caixa de citação desenhados sobre a ilustração **e que fica
   dentro da `box`** precisa de `text` (letras soltas) ou `fill` (bloco sólido). Retângulos podem
   passar da `box` (o inpaint é feito na imagem inteira).
4. Uma imagem pode render vários recortes (ex.: vilão à esquerda e mulher à direita da capa;
   emblema e personagem na imagem final).
5. Para `panorama`, recorte a faixa larga inteira (proporção ≥ 2:1) — a câmera a atravessa.
6. Para `opening` com duas camadas, dois recortes de proporção próxima de 1:1.

## Conferir

Rode `arte --previa`: gera `.estudio/arte_previa_<n>.jpg` com, para cada recorte, a região original
(à esquerda, **ciano** = pixels apagados, com contorno) e o recorte final (à direita). Confira:

- nenhum resto de letra, sublinhado ou canto de caixa no recorte final;
- nenhuma linha de moldura nas bordas;
- o inpaint não borrou rosto/mãos/elemento importante (se borrou, diminua o retângulo `text`/`fill`
  ou mude a `box` para deixar o texto de fora);
- a ilustração inteira que importa está dentro da `box`.

Depois de mudar `arte.json`: `arte --so recortes --previa` (rápido) e, se mudou alguma `box`,
`arte --so profundidade` (o mapa de profundidade é refeito só para recortes alterados).
