---
name: preparar-estudio
description: Instala, atualiza e diagnostica o motor do plugin estudio-video (Remotion + Chrome headless, Real-ESRGAN, modelo de profundidade, detector de rosto, fontes das legendas, modelo de transcrição, ffmpeg, dependências Python via uv). Use quando o usuário pedir para instalar/configurar/atualizar o estúdio de vídeo, quando `verificar` mostrar itens faltando, ou quando um comando do motor falhar por ambiente (ffmpeg, Vulkan/GPU, npm, Chrome, disco).
---

# Preparar o estúdio

Motor: `uv run --python 3.12 "${CLAUDE_PLUGIN_ROOT}/motor/estudio.py" --dados "${CLAUDE_PLUGIN_DATA}" <comando>`

## Instalar ou atualizar

1. `… verificar` — lista cada requisito com ✓/✗.
2. `… setup` — idempotente; baixa só o que falta:
   - copia o template do Remotion para `${CLAUDE_PLUGIN_DATA}/video` e roda `npm ci`
     (~810 MB com o Chrome headless);
   - Real-ESRGAN (~47 MB) + teste na GPU (Vulkan) e modelo de profundidade (~99 MB) em
     `${CLAUDE_PLUGIN_DATA}/ferramentas/`;
   - YuNet (~230 KB), o detector de rosto do modo vídeo: é o que faz a câmera seguir quem fala em
     vez de ficar parada — sem ele o movimento automático simplesmente não acontece;
   - três fontes livres para as legendas queimadas (~350 KB no total) em
     `${CLAUDE_PLUGIN_DATA}/ferramentas/tipografias/`: `Barlow-Bold.ttf` (padrão),
     `Anton-Regular.ttf` (condensada, para legenda grande) e `ArchivoBlack-Regular.ttf` (pesada).
     Sem elas a legenda cai na fonte do sistema (`captions.font`);
   - ffmpeg estático (~40 MB de download) **só** se não houver ffmpeg no sistema nem no flatpak do Kdenlive.

   O modelo de transcrição do modo vídeo (~1,5 GB no padrão `medium`) **não** entra no setup: ele é
   baixado no primeiro `transcrever`, para `${CLAUDE_PLUGIN_DATA}/ferramentas/whisper/`.
3. Flags: `--forcar` (reinstala dependências do Remotion), `--sem-ia` (não baixa Real-ESRGAN nem o
   modelo de profundidade; o motor usa Lanczos e desliga a paralaxe 2.5D). O detector de rosto e as
   fontes são baixados sempre: são pequenos e não são de IA generativa.

Requisitos que o setup não instala: **uv** (`curl -LsSf https://astral.sh/uv/install.sh | sh`) e
**Node.js ≥ 18**. Peça ao usuário para instalar com `! <comando>` se faltarem.
O template é sincronizado automaticamente a cada comando — atualizar o plugin não exige setup, a não
ser que `package.json` do motor mude (o próprio comando reinstala nesse caso).

## Problemas conhecidos

| Sintoma | Causa e solução |
|---|---|
| `VK_ERROR_DEVICE_LOST` / ampliação cai para Lanczos | GPU integrada sem tempo para blocos grandes; o motor já usa `-t 64`. Sem Vulkan funcional, Lanczos é automático (qualidade menor, funciona) |
| `ffmpeg falhou` com caminho em `/tmp` | ffmpeg do flatpak só enxerga a pasta pessoal: mantenha projeto e dados dentro de `~` |
| `verificar` acusa `ffmpeg: x264/aac/legendas` | build de ffmpeg sem libx264/libass (o modo vídeo precisa dos dois para cortar e queimar legenda): rode `… setup`, que baixa o estático |
| legenda queimada com fonte errada | a fonte de `projeto.json → captions.font` não está instalada no sistema (ou não é vista pelo flatpak); use uma fonte instalada, `DejaVu Sans` sempre existe |
| `transcrever` muito lento | modelo grande na CPU: `--modelo small` corta o tempo (menos preciso em nomes próprios) |
| `qa` falha em `quadros = timeline` (modo vídeo) | algum tempo escapou da grade de quadros: refaça `montar` e `render --forcar` |
| `edge-tts falhou` | serviço online (rede ou limite); tente de novo em instantes. O cache evita refazer falas já geradas |
| `arte "x" não existe em art.json` no render | recorte novo sem rodar `arte --so recortes` |
| erro de Chrome/`browser` no render | `… setup` (roda `remotion browser ensure`) |
| disco cheio | o `.estudio/` de projetos já entregues pode ser apagado (é regenerável); `saida/` é o que importa |
| render muito lento ou sem memória | `projeto.json` → `render.concurrency` menor (padrão 6) |

Para uso sem o Claude: `ESTUDIO_DADOS=<dir> uv run --python 3.12 <plugin>/motor/estudio.py --help`.
