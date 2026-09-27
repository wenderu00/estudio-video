# Revisão: quadros e vídeo final

Eu (Claude) não consigo ouvir o áudio: a escuta final é do usuário. Todo o resto se confere assim.

## Quadros de revisão (`quadros`)

`quadros --formato main` (e `--formato shorts`) renderiza, sem gerar o vídeo, o meio de cada
transição, o **último quadro de cada fala** (todo o texto daquela fala já revelado) e o fim de cada
cena, e monta folhas de contato em `.estudio/quadros/folha_<formato>_NN.jpg` com rótulo
`#quadro tempo cena fala (papel)`. Para olhar de perto: `quadros --formato main 537 859` (quadros
avulsos, salvos em `.estudio/quadros/<formato>/<quadro>.jpg`) ou `--cenas cap1,cap2`.

### O que procurar

| Problema | Onde corrigir |
|---|---|
| texto cortado na borda, sobreposto a outro texto ou ao rosto | `style` (`fontSize`, `quoteSize`, `quoteWidth`), `screenText` mais curto, ou câmera (`x`/`y`) |
| texto ilegível sobre fundo claro | `backdrop`, câmera para área mais escura, `fog.opacity` menor |
| borda/moldura/resto de letra da imagem original aparecendo | `arte.json` (`box` para dentro, `text`/`fill`) |
| câmera mostrando fundo além da imagem sem querer | `x`/`y` entre −1 e 1, ou `s` maior |
| destaque (`hl`) na palavra errada | `hl`/`hlFrom` da fala (comparação ignora acento e pontuação) |
| cena vazia por tempo demais / texto some cedo | `preRoll`, `postRoll`, `pause` |
| Shorts: texto nos ~200 px do topo ou nos ~420 px de baixo, ou na coluna de botões à direita | layout do Shorts é fixo e seguro; o risco é `screenText` longo demais — encurte |
| transição “suja” (duas cenas misturando texto) | normal durante 0,3–0,5 s; se incomodar, aumente `postRoll` da cena anterior ou `preRoll` da próxima |

Quadros no **meio de transições** parecem estranhos por natureza (dupla exposição, borrões) —
julgue-os pela intenção, não como quadro final.

## Vídeo final (`qa`)

`qa` confere cada mp4 contra a timeline e imprime ✓/✗:

- resolução, fps, `yuv420p`, AAC 48 kHz, número de quadros = timeline;
- loudness integrado −14 LUFS (±1) e pico real ≤ −1 dBTP (padrão do YouTube);
- `faststart` (começa a tocar antes de baixar tudo);
- Shorts ≤ 60 s;

e gera folhas de contato em `.estudio/qa/folha_<formato>_NN.jpg` (1 quadro a cada 4 s no 16:9, 2 s
no Shorts) para uma última olhada no vídeo inteiro.

Relatório de áudio da mixagem (`mix`): além do loudness, mostra quantos dB a voz fica acima da
trilha durante as falas (bom: ≥ 12 dB). O espectrograma com os cortes de cena fica em
`.estudio/work/espectrograma_<formato>.png`.
