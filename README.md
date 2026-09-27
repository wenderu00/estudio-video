# estudio-video

<p align="center"><img src="docs/demo.gif" width="270" alt="Trecho do Shorts de exemplo, gerado pelo plugin a partir de uma sequência de imagens"></p>

Plugin de Claude Code com dois modos de produção, o mesmo motor e a mesma conferência de qualidade:

- **modo imagens** — uma **sequência de imagens** (cards ilustrados, quadrinhos, artes com texto)
  vira um **vídeo narrado para o YouTube** (1920×1080) e um **Shorts** (1080×1920): roteiro,
  narração neural em português, trilha sonora original composta por código, motion design com
  paralaxe 2.5D e transições, legendas `.srt`;
- **modo vídeo** — uma **gravação bruta com fala** (aula, entrevista, podcast em vídeo, captura de
  tela narrada) vira um **vídeo editado e acabado**: transcrição local, cortes escolhidos pelos
  índices da transcrição, correção de cor com vinheta e grão, movimento de câmera que segue quem
  fala, 18 transições, chips de seção, tarja, callouts, cards, marca-d'água e tela final, legendas
  queimadas no estilo do material, b-roll, trilha e mixagem −14 LUFS.

Tudo sem editor de vídeo e sem banco de mídia.

Nasceu do vídeo “Um Vilão Memorável: o que faria tudo por ela”, que está incluído como exemplo
(`exemplos/um-vilao-memoravel/`) e é reproduzido pelo motor genérico quadro a quadro, com a trilha
idêntica bit a bit.

## Como usar — modo vídeo (gravação bruta)

Numa pasta com a gravação, peça ao Claude:

> edita esse vídeo pra mim, tira os silêncios e os erros

ou use `/estudio-video:editar-video [pasta] [observações]`. O fluxo:

1. cria o projeto a partir da gravação (`novo --video`) e lê resolução, fps e duração;
2. **transcreve a fala localmente** (faster-whisper, CPU) e marca silêncios, hesitações e repetições;
3. o **montador** escreve `corte.json` — quais trechos ficam, em que ordem, com que transição;
4. você aprova o corte;
5. o acabamento e a legenda são ajustados ao material (`projeto.json → look`, `camera`, `brand`,
   `captions`) — o padrão já entrega cor tratada, vinheta, grão e um movimento suave de câmera onde
   há rosto na tela;
6. o motor monta a timeline, corta a voz na mesma grade de quadros, gera `.srt`/`.ass`, trilha e mixagem;
7. o **revisor de quadros** confere as folhas de contato;
8. render (ffmpeg corta, trata e junta; só os trechos com overlay passam pelo Remotion) +
   conferência automática, que agora também mede contraste e saturação e avisa quando a imagem
   saiu chapada.

Um vídeo bruto de 20 minutos renderiza em minutos, não em horas.

## Como usar — modo imagens

Numa pasta com as imagens (em ordem: `1.jpg`, `2.jpg`… ou dentro de `imagens/`), peça ao Claude:

> crie um vídeo para o YouTube com essas imagens

ou use `/estudio-video:criar-video [pasta] [observações]`. O fluxo:

1. confere/instala o ambiente (primeira vez: alguns minutos, ~1 GB);
2. pergunta o essencial (voz, Shorts, duração, fidelidade ao texto das imagens) e cria `projeto.json`;
3. o **roteirista** escreve o roteiro enquanto o **diretor de arte** define os recortes das imagens;
4. você aprova o roteiro;
5. o diretor de arte dá câmera, camadas, partículas e impactos a cada cena;
6. o motor gera arte, narração, timeline, trilha e mixagem (−14 LUFS);
7. o **revisor de quadros** confere folhas de contato e aponta problemas até não sobrar nenhum;
8. render final + conferência automática (specs, loudness, faststart, Shorts ≤ 60 s).

Para mudar algo depois (“música mais baixa”, “voz mais lenta”, “troca esse texto”), peça — a skill
`ajustar-video` sabe qual arquivo mudar e qual etapa refazer.

## Instalação

```bash
claude plugin marketplace add wenderu00/estudio-video
claude plugin install estudio-video@estudio-video
```

(ou `/plugin marketplace add …` e `/plugin install …` dentro do Claude Code). Requisitos no sistema:
**uv**, **Node.js ≥ 18** e, de preferência, uma GPU com Vulkan (para o Real-ESRGAN; sem ela o motor
amplia com Lanczos). O resto — dependências do Remotion, Chrome headless, Real-ESRGAN, modelo de
profundidade, detector de rosto, três fontes para as legendas e, se faltar, um ffmpeg estático — o
próprio plugin instala em `${CLAUDE_PLUGIN_DATA}`
(`~/.claude/plugins/data/estudio-video-estudio-video/`), uma única vez para todos os projetos.

## Estrutura

```
estudio-video/
├── .claude-plugin/        plugin.json + marketplace.json (marketplace de diretório)
├── skills/
│   ├── criar-video/       modo imagens: fluxo completo (+ references/: roteiro.md, arte.md, revisao.md)
│   ├── editar-video/      modo vídeo: fluxo completo (+ references/corte.md)
│   ├── preparar-estudio/  instalação, atualização e diagnóstico do motor
│   └── ajustar-video/     mudanças depois do render, nos dois modos
├── agents/
│   ├── roteirista-video.md       imagens → roteiro.json / roteiro_shorts.json
│   ├── diretor-de-arte-video.md  grades → arte.json; visual das cenas
│   ├── montador-video.md         transcrição → corte.json
│   └── revisor-de-quadros.md     avaliador: folhas de contato → problemas + correção
├── motor/
│   ├── estudio.py         CLI (setup, novo, validar, grades, arte, narracao, timeline, trilha,
│   │                      mix, preparar, quadros, render, qa)
│   ├── pipeline/          Python 3.12 via uv: ambiente, projeto (formato + validação), arte,
│   │                      narracao (edge-tts), timeline (âncoras → quadros), synth + trilha
│   │                      (instrumentos e climas), mix (voz, ducking, master), remotion, qa;
│   │                      no modo vídeo: fonte (ffprobe/áudio/silêncio), transcricao
│   │                      (faster-whisper), corte (timeline + voz + legendas), enquadre (onde
│   │                      está quem fala), montagem (corte, acabamento e transições em ffmpeg)
│   └── video/             template Remotion 4 (React/TS) que lê a timeline do projeto via --props
└── exemplos/
    ├── um-vilao-memoravel/    modo imagens: projeto.json, roteiro.json, roteiro_shorts.json, arte.json
    └── edicao-de-gravacao/    modo vídeo: projeto.json, corte.json (a gravação não é versionada)
```

## Um projeto

Tudo que é específico de um vídeo mora na pasta do projeto, em três arquivos de dados — o código do
motor não muda de um vídeo para outro:

```
meu-video/
├── 1.jpg … N.jpg            imagens de entrada (ou imagens/)
├── projeto.json             título, imagens, vozes, paleta, trilha, mixagem
├── roteiro.json             cenas 16:9: falas, papéis em tela, câmera, efeitos, transições, trilha
├── roteiro_shorts.json      cenas 9:16 (opcional)
├── arte.json                recortes das imagens e textos a apagar
├── .estudio/                cache regenerável (ampliações, narração, trilhas, quadros de revisão)
└── saida/                   <slug>.mp4, <slug>-shorts.mp4, .srt, roteiro.md, narracao.wav, trilha-sonora.wav
```

No modo vídeo os arquivos de dados são dois:

```
meu-video/
├── bruto.mp4                gravação de entrada (mais b-roll, se houver)
├── projeto.json             título, `modo: "video"`, sources, acabamento (`look`), câmera, marca
│                            (`brand`), estilo da legenda, trilha, mixagem
├── corte.json               seções e segmentos que ficam: in/out na fonte, transições, câmera,
│                            trilha, overlays
├── .estudio/                cache: transcrição, sugestões, voz editada, clipes de corte, master
└── saida/                   <slug>.mp4, <slug>.srt, transcricao.md, narracao.wav, trilha-sonora.wav
```

O formato completo está em `skills/criar-video/references/roteiro.md` e `arte.md` (modo imagens) e em
`skills/editar-video/references/corte.md` (modo vídeo). Para usar o motor sem o Claude:
`ESTUDIO_DADOS=<dir> uv run --python 3.12 motor/estudio.py --help`.

## Tempos de referência

Ryzen 7 8700G (16 threads) + Radeon 780M, vídeo de 2:30 + Shorts de 46 s: ampliação 4× das 7 imagens
~2 min, narração ~20 s (40 falas), trilha ~35 s, mixagem ~12 s, quadros de revisão ~1 min, render
~35 min (16:9) + ~10 min (Shorts).

## Desenvolvimento

- O plugin é carregado direto desta pasta (marketplace de diretório): edições valem na próxima
  sessão (ou `/reload-plugins`). O template do Remotion é copiado para `${CLAUDE_PLUGIN_DATA}/video`
  automaticamente a cada comando; se mudar `motor/video/package.json`, atualize o
  `package-lock.json` (o próximo comando reinstala as dependências).
- Tudo que é de um vídeo específico tem que caber nos dados (`projeto.json`, `roteiro*.json`,
  `arte.json`). Um recurso novo entra no motor com valor padrão, e o formato é documentado em
  `skills/criar-video/references/`.
- Testes de regressão: `exemplos/um-vilao-memoravel` para o modo imagens (a timeline tem de sair
  byte a byte igual) e `exemplos/edicao-de-gravacao` para o modo vídeo (4130 quadros, `qa` com
  todos os ✓). Veja o README de cada um. `npx tsc --noEmit` em
  `${CLAUDE_PLUGIN_DATA}/video` confere os tipos; `claude plugin validate . --strict` confere o plugin.

## Licenças e cuidados

- Código do plugin: do autor. YuNet, o detector de rosto (OpenCV Zoo, MIT), e as fontes das
  legendas — Barlow, Anton e Archivo Black (SIL OFL) — são baixados no `setup`.
  Remotion: gratuito para pessoa física e empresas de até 3 pessoas
  (acima disso, licença de empresa). Real-ESRGAN (BSD-3), Depth Anything V2 Small (Apache-2.0),
  fontes do Google Fonts e ícones Lucide: licenças livres.
- A trilha e os efeitos são sintetizados por código a cada vídeo — originais, sem risco de Content ID.
- A narração usa o **edge-tts**, cliente não oficial do “ler em voz alta” do Microsoft Edge: o texto
  do roteiro é enviado ao serviço, e o uso comercial dessas vozes por esse caminho não tem licença
  clara. Para canal monetizado, o caminho seguro é o Azure Speech (mesmas vozes, pago) — a troca
  ficaria restrita a `motor/pipeline/narracao.py`.
- O Claude não ouve áudio: a escuta final da narração e da trilha é humana.
