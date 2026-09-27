---
name: editar-video
description: Edita uma gravação bruta (aula, entrevista, podcast em vídeo, gravação de tela com narração) e entrega um vídeo cortado, com legendas queimadas, trilha e mixagem −14 LUFS — transcrevendo a fala, cortando pelos índices da transcrição e montando com ffmpeg. Use quando o usuário pedir para editar/cortar/limpar um vídeo que já existe, tirar silêncios e erros de uma gravação, ou "transformar esse bruto num vídeo publicável".
argument-hint: "[arquivo ou pasta da gravação] [observações]"
---

# Editar um vídeo bruto

**Motor** (sempre por extenso — variáveis do shell não persistem entre comandos):
`uv run --python 3.12 "${CLAUDE_PLUGIN_ROOT}/motor/estudio.py" --dados "${CLAUDE_PLUGIN_DATA}" <comando> --projeto <PASTA>`
Abaixo, `EV <comando>` abrevia isso. `<PASTA>` = pasta absoluta do projeto (onde está a gravação).

Referências:
- `${CLAUDE_PLUGIN_ROOT}/skills/editar-video/references/corte.md` — formato de `corte.json`, âncoras, overlays, legendas
- Para criar vídeo **a partir de imagens**, a skill é outra: `criar-video`.

## Fluxo

Copie e marque o progresso:
```
- [ ] 1. Ambiente pronto (verificar/setup)
- [ ] 2. Projeto criado a partir da gravação
- [ ] 3. Transcrição + sugestões de corte
- [ ] 4. Corte escrito (montador) e aprovado pelo usuário
- [ ] 5. Acabamento (look/marca) e legenda definidos a partir do material
- [ ] 6. preparar (timeline, voz editada, legendas, trilha, mix)
- [ ] 7. Quadros revisados e corrigidos
- [ ] 8. Render + qa
- [ ] 9. Entrega
```

1. **Ambiente**: `EV verificar`. Itens obrigatórios aqui: ffmpeg com **x264, aac e legendas (libass)**.
   Se faltar, `EV setup` baixa um ffmpeg estático. Com ffmpeg vindo do flatpak, o projeto precisa
   estar dentro da pasta pessoal.
2. **Projeto**: `EV novo --video <arquivo> --projeto <PASTA> --titulo "<título>"` (sem valor em
   `--video`, ele detecta a maior gravação da pasta). O comando imprime resolução, fps e duração da
   fonte — confira com o usuário se a saída deve mesmo ser nesse tamanho. Registre b-roll extra em
   `projeto.json → sources`.
3. **Transcrição**: `EV transcrever` **em segundo plano** (CPU; conte ~1/3 da duração do áudio com o
   modelo padrão `medium`, menos com `--modelo small`). Saem `saida/transcricao.md`,
   `.estudio/transcricao.json` e `.estudio/sugestoes.json`. O áudio não sai da máquina.
4. **Corte**: despache o agente `montador-video` com a pasta, as observações do usuário e a duração
   alvo. Depois **mostre ao usuário o que sai e o que fica** (por assunto, com a duração estimada) e
   peça OK antes de gastar render.
5. **Acabamento e legendas**: abra 2–3 quadros da gravação (`EV quadros` ainda não; use ffmpeg ou
   olhe o vídeo) e **olhe mesmo** — é um julgamento visual, não de log.
   - `projeto.json → look`: o padrão é `natural`. Se a imagem está fria, chapada ou estourada,
     escolha outro preset (`quente`, `frio`, `cinema`, `limpo`) ou ajuste os números soltos. Se o
     usuário já tem uma correção de cor pronta, aponte `look.lut` para o `.cube` dele.
   - `projeto.json → camera`: o padrão move a câmera 6% onde há rosto. Captura de tela nunca é
     mexida. Desligue com `auto: false` se o enquadramento já for apertado.
   - `projeto.json → brand`: `logo`, `name`, `handle`, `color`. Com logo, entram marca-d'água e a
     tela final (`tela_final` em segundos). Sem material de marca, deixe vazio — não invente.
   - `projeto.json → captions`: fonte, corpo, cor, contorno/caixa e posição que funcionem sobre
     aquela imagem — legenda clara sobre fundo claro é o erro mais comum. Se o usuário deu
     referência de estilo (um vídeo, uma marca, um print), siga-a.
6. **Preparar**: `EV preparar` (valida, monta a timeline, corta a voz, escreve `.srt`/`.ass`, gera
   trilha e mixagem). Anote a duração final e o relatório de áudio (−14 LUFS; voz ≥ 12 dB acima da
   trilha). Música alta demais ou de menos: `mix.music_lufs`.
7. **Quadros**: `EV quadros` (amostra o vídeo montado com as legendas) e despache `revisor-de-quadros`
   com as folhas `.estudio/quadros/folha_*.jpg`. Corrija o que ele apontar — a skill `ajustar-video`
   diz o que refazer — e revise de novo só as cenas afetadas (`--cenas`).
8. **Render**: `EV render` **em segundo plano** (minutos, não horas: o ffmpeg faz o corte e só os
   trechos com overlay passam pelo Remotion). Confira o espaço em disco antes: o corte, o master e
   os clipes de overlay convivem em `.estudio/` e somam alguns GB num vídeo longo. Depois `EV qa`. Todos os ✓ são obrigatórios — em
   especial `quadros = timeline`, que é a prova de que imagem e som continuam em sincronia. Passe as
   folhas de `.estudio/qa/` ao revisor para a olhada final.
9. **Entrega**: liste os arquivos de `<PASTA>/saida/` (mp4, `.srt`, `transcricao.md`, narração e
   trilha separadas), duração antes e depois do corte, formato e loudness; diga que você não ouve o
   áudio e que a escuta final é do usuário; lembre que o `.srt` sobe como legenda no YouTube mesmo
   com a legenda já queimada.

## Regras

- Não edite o código do motor para um vídeo: tudo é dado em `projeto.json` e `corte.json`.
- Mudar `look` refaz os clipes do corte (o nome deles carrega o hash do filtro) — é rápido, e é o
  que garante que a mudança apareça. Mudar só overlays não refaz o corte.
- Depois de qualquer edição de JSON: `EV validar`.
- Não apague `.estudio/` durante o trabalho (é cache, e a transcrição mora lá).
- Nunca invente fala: o corte só escolhe trechos do que foi dito. Se faltar uma frase, o caminho é
  gravar de novo ou assumir a falta — não "consertar" no texto.
- A transcrição erra nomes próprios, números e siglas. Confira esses pontos na legenda antes de
  entregar.
