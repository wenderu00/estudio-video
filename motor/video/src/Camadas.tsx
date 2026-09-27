import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { clamp } from "./lib/anim";
import { Cartao, Destaque, Imagem, Titulo } from "./overlays/basicos";
import { Callout, Card, Secao, Tarja } from "./overlays/estrutura";
import { TelaFinal, Vinheta } from "./overlays/marca";
import { setZonaLegenda } from "./overlays/comuns";
import { setPalette } from "./theme";
import type { Brand, CamadasProps, Overlay } from "./types";

/** Overlays for the video mode: rendered alone, over a transparent background, and composited on
 *  the cut master by ffmpeg. Only the frames that actually carry an overlay go through Chrome —
 *  which is why anything lasting the whole video (watermark, progress bar) lives in montagem.py
 *  as an ffmpeg filter instead of here. */

type Comp = React.FC<{ o: Overlay; dur: number; brand?: Brand }>;

const POR_TIPO: Record<string, Comp> = {
  cartao: Cartao,
  titulo: Titulo,
  destaque: Destaque,
  imagem: Imagem,
  secao: Secao,
  tarja: Tarja,
  callout: Callout,
  card: Card,
  vinheta: Vinheta,
  telaFinal: TelaFinal,
};

export const CamadasComp: React.FC<CamadasProps> = (props) => {
  setPalette(props.palette);
  setZonaLegenda(props.capBase);
  return (
    <AbsoluteFill>
      {props.overlays.map((o) => {
        const Comp = POR_TIPO[o.kind] ?? Cartao;
        return (
          <Sequence key={o.id} from={o.rel} durationInFrames={o.durFrames} name={`${o.kind} ${o.id}`} layout="none">
            <Comp o={o} dur={o.durFrames} brand={props.brand} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

export { clamp };
