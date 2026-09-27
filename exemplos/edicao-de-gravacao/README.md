# Exemplo do modo vídeo — “Teste de Mutação”

O que `exemplos/um-vilao-memoravel/` é para o modo imagens, este é para o **modo vídeo**: um corte
real, completo e validado, que serve de referência de formato e de **teste de regressão**.

A gravação não está aqui (são 43 MB de webcam falando por 2:39). O que está versionado são os dois
arquivos de dados que um projeto do modo vídeo tem:

```
edicao-de-gravacao/
├── projeto.json    modo vídeo, acabamento (look), câmera, marca, legenda, trilha, mixagem
└── corte.json      4 seções + 5 segmentos: transições, câmera, look por trecho e 6 overlays
```

## O que ele exercita

| Recurso | Onde |
|---|---|
| `sections` que abrem segmentos | as 4 seções, cada uma com uma transição diferente |
| transições | `fadeFromBlack`, `crossfade` (via `dissolve`), `wipeDiagonal`, `zoomPunch`, `whipLeft`, `fadeToBlack` |
| câmera explícita | `hold` (reenquadre mais fechado) em `problema`, `snap` (zoom de impacto) em `custo` |
| câmera automática | `oquee` e `solucao` não declaram `camera` e recebem `punch`/`pull` alternados, porque há rosto na tela |
| `look` por segmento | `solucao` usa o preset `cinema` sobre o `natural` do projeto |
| overlays | `vinheta`, `tarja`, `cartao`, `callout`, `card`, `destaque` (+ `secao` e `telaFinal`, gerados pelo motor) |
| marca | `brand` com barra de progresso e tela final de 6 s |

## Como usar

Numa pasta com a sua gravação chamada `bruto.mp4` (ou ajuste `sources` em `projeto.json`):

```bash
cp exemplos/edicao-de-gravacao/*.json <SUA_PASTA>/
EV transcrever --projeto <SUA_PASTA>      # os índices w: mudam com a sua fala
EV validar --projeto <SUA_PASTA>
```

As âncoras `w:` de `corte.json` apontam para as palavras **daquela** gravação — num material
diferente elas caem no lugar errado, ou a validação recusa. Trate o `corte.json` como **modelo de
formato**, não como corte pronto: copie a estrutura e deixe o montador escolher os tempos.

Para `brand.logo`, aponte para um PNG da sua pasta; aqui ele fica vazio de propósito, para não
versionar binário de marca de ninguém.

## Como regressão

Com a gravação original no lugar, `EV montar` tem de produzir uma timeline com **4130 quadros** em
30 fps (2:17,7), e `EV qa`, depois do render, tem de fechar com todos os ✓ — em especial
`quadros = timeline`, que é a prova de que imagem e som seguem em sincronia depois de todas as
transições, movimentos de câmera e overlays.
