# Exemplo: “Um Vilão Memorável: o que faria tudo por ela”

Vídeo de 2:30 (16:9) + Shorts de 46 s feito a partir de 7 cards ilustrados. Os arquivos daqui são o
projeto completo, **sem as imagens** (elas são do autor e ficam fora do plugin).

- `projeto.json` — 3 vozes (narrador, vilão com `fx: sombrio`, heroína com `fx: sala`), trilha em ré
  menor com o tema padrão.
- `arte.json` — 9 recortes: duas figuras da capa, a arte de cada capítulo (com texto e caixas de
  citação apagados), a panorâmica e, da última imagem, o sigilo (`alpha: luma`) e o vilão ajoelhado.
- `roteiro.json` — abertura com duas camadas, 4 capítulos, panorama, moral com emblema e
  encerramento, com câmeras, partículas e beats ancorados na narração.
- `roteiro_shorts.json` — versão 9:16 condensada.

Para reproduzir, com as imagens `1.jpeg` … `7.jpeg` numa pasta:

```bash
EV="uv run --python 3.12 <plugin>/motor/estudio.py"
$EV novo --projeto <pasta> --exemplo um-vilao-memoravel
$EV preparar --projeto <pasta>
$EV quadros --projeto <pasta> --formato main
$EV render --projeto <pasta> --formato ambos && $EV qa --projeto <pasta>
```

É também o teste de regressão do motor: com a mesma narração em cache, a timeline sai com os mesmos
quadros e as trilhas saem idênticas bit a bit às do vídeo original.
