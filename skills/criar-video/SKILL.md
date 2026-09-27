---
name: criar-video
description: Cria um vídeo narrado para YouTube (16:9) e, opcionalmente, um Shorts (9:16) a partir de uma sequência de imagens — roteiro, narração neural pt-BR, trilha original, motion design com transições, legendas .srt e conferência de qualidade — usando o motor do plugin estudio-video. Use quando o usuário pedir para criar/fazer/montar um vídeo, vídeo para YouTube, Shorts ou "vídeo com essas imagens" a partir de imagens ou cards numa pasta.
argument-hint: "[pasta das imagens] [observações]"
---

# Criar vídeo a partir de imagens

> Se a entrada for uma **gravação de vídeo** (aula, entrevista, captura de tela com fala) e não uma
> sequência de imagens, a skill é a `editar-video`.

**Motor** (sempre por extenso — variáveis do shell não persistem entre comandos):
`uv run --python 3.12 "${CLAUDE_PLUGIN_ROOT}/motor/estudio.py" --dados "${CLAUDE_PLUGIN_DATA}" <comando> --projeto <PASTA>`
Abaixo, `EV <comando>` abrevia isso. `<PASTA>` = pasta absoluta do projeto (onde estão as imagens).

Referências (leia a que a etapa pedir; passe os caminhos aos agentes):
- `${CLAUDE_PLUGIN_ROOT}/skills/criar-video/references/roteiro.md` — formato de projeto/roteiro
- `${CLAUDE_PLUGIN_ROOT}/skills/criar-video/references/arte.md` — recortes (`arte.json`)
- `${CLAUDE_PLUGIN_ROOT}/skills/criar-video/references/revisao.md` — revisão de quadros e QA
- Exemplo completo: `${CLAUDE_PLUGIN_ROOT}/exemplos/um-vilao-memoravel/`

## Fluxo

Copie e marque o progresso:
```
- [ ] 1. Ambiente pronto (verificar/setup)
- [ ] 2. Decisões + projeto.json
- [ ] 3. Roteiro (roteirista) e recortes (diretor de arte, fase recortes) em paralelo
- [ ] 4. Roteiro aprovado pelo usuário
- [ ] 5. Visual das cenas (diretor de arte, fase cenas)
- [ ] 6. preparar (arte, narração, timeline, trilha, mix)
- [ ] 7. Quadros revisados e corrigidos
- [ ] 8. Render + qa
- [ ] 9. Entrega
```

1. **Ambiente**: `EV verificar`. Se algo essencial estiver ✗, rode `EV setup` (alguns minutos, ~1 GB;
   veja a skill `preparar-estudio` se falhar). Com ffmpeg vindo do flatpak, o projeto precisa estar
   dentro da pasta pessoal.
2. **Decisões**: olhe as imagens (Read) para entender a história. Pergunte numa só rodada
   (AskUserQuestion) apenas o que muda o trabalho: voz do narrador, se quer Shorts, duração-alvo,
   fidelidade ao texto das imagens. Sem resposta, use: narrador masculino grave, com Shorts, 2–3 min,
   fiel ao texto. Depois `EV novo --titulo "<título>"`; confira em `projeto.json` se `images` está na
   ordem da história e ajuste `voices` conforme os personagens que falam.
3. **Roteiro e recortes, em paralelo** (duas chamadas de Agent na mesma mensagem; os dois já sabem
   a convenção: recorte principal da imagem N = `img<N>`, extras = `img<N>_<nome>`):
   - `roteirista-video`: pasta, decisões, lista de imagens com o que cada uma mostra. Ele escreve
     `roteiro.json` (+ `roteiro_shorts.json`) e valida.
   - `diretor-de-arte-video` com **fase recortes**: gera grades, escreve `arte.json`, amplia, recorta e
     confere a prévia.
4. **Aprovação**: mostre o roteiro ao usuário (cena → falas, curto) e peça OK antes de gerar a
   narração — o texto vai para o serviço online de voz da Microsoft.
5. **Visual**: `diretor-de-arte-video` com **fase cenas**: adiciona câmera, camadas, partículas, beats
   e transições às cenas dos roteiros, usando os recortes.
6. **Preparar**: `EV preparar` (valida e roda arte, narração, timeline, trilha e mix; 1–3 min com
   cache). Anote a duração de cada formato e o relatório de áudio (−14 LUFS; voz ≥ 12 dB acima da
   trilha). Shorts acima de 60 s: peça ao roteirista para encurtar.
7. **Quadros**: `EV quadros --formato main` e `EV quadros --formato shorts`; despache
   `revisor-de-quadros` com os caminhos das folhas `.estudio/quadros/folha_*.jpg`. Corrija o que ele
   apontar (a skill `ajustar-video` diz qual arquivo mudar e o que refazer) e revise de novo só as
   cenas afetadas (`--cenas`). Repita até não haver problema real.
8. **Render**: `EV render --formato ambos` **em segundo plano** (run_in_background; leva ~10–15× a
   duração do vídeo) e depois `EV qa`. Todos os ✓ são obrigatórios. Passe as folhas de
   `.estudio/qa/` ao revisor para a olhada final.
9. **Entrega**: liste os arquivos de `<PASTA>/saida/` (mp4, .srt, `roteiro.md`, narração e trilha
   separadas), duração, formato e loudness; diga que você não ouve áudio e que a escuta final é do
   usuário; lembre que o `.srt` sobe como legenda no YouTube e que os últimos ~10 s do 16:9 ficam
   livres para a tela final.

## Regras

- Não edite o código do motor para um vídeo; tudo é dado em `projeto.json`, `roteiro*.json`,
  `arte.json`. Se faltar um recurso de verdade, diga ao usuário.
- Depois de qualquer edição de JSON: `EV validar`.
- Não apague `.estudio/` durante o trabalho (é cache); ele é regenerável depois da entrega.
- As vozes vêm do edge-tts (cliente não oficial do “ler em voz alta” do Edge): para canal
  monetizado, avise que o uso comercial não tem licença clara.
