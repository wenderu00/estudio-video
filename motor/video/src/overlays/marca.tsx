import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { easeOut, pop, prog } from "../lib/anim";
import { accent as accentOf, rgba } from "../theme";
import type { Brand, Overlay } from "../types";
import { SOMBRA, fadeBorda, tipoCorpo, tipoTitulo, useMargem } from "./comuns";

type P = { o: Overlay; dur: number; brand?: Brand };

/** Opening sting: the channel's colour sweeps across, the mark lands, and it clears out. */
export const Vinheta: React.FC<P> = ({ o, dur, brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { height, width } = useMargem();
  const cor = accentOf(o.accent ?? brand?.color ?? "red");
  const entra = prog(frame, 0, Math.max(6, Math.round(dur * 0.35)), easeOut);
  const sai = prog(frame, Math.round(dur * 0.62), Math.max(6, Math.round(dur * 0.38)), easeOut);
  const marca = pop(frame, Math.round(dur * 0.22), fps, 13, 180);
  const cobertura = Math.min(entra, 1 - sai);
  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          background: `linear-gradient(105deg, ${cor} 0%, ${rgba("#07070A", 0.96)} 62%)`,
          clipPath: `inset(0 ${((1 - entra) * 100).toFixed(1)}% 0 ${(sai * 100).toFixed(1)}%)`,
        }}
      />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: cobertura }}>
        <div style={{ textAlign: "center", transform: `scale(${(0.9 + 0.1 * marca).toFixed(3)})`, opacity: marca, filter: SOMBRA }}>
          {brand?.logo ? (
            <Img src={staticFile(brand.logo)} style={{ height: height * 0.18, objectFit: "contain", marginBottom: height * 0.03 }} />
          ) : null}
          <div style={{ ...tipoTitulo(height * 0.085), fontWeight: 700, textTransform: "uppercase", letterSpacing: 3, maxWidth: width * 0.8 }}>
            {o.title ?? brand?.name}
          </div>
          {(o.sub ?? brand?.handle) ? (
            <div style={{ ...tipoCorpo(height * 0.035), marginTop: height * 0.016, letterSpacing: 4, color: rgba(cor, 0.95) }}>
              {o.sub ?? brand?.handle}
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** Closing card.
 *
 *  YouTube draws its own end cards over the last seconds, and they sit in the middle and on the
 *  right — so everything here stays in the left third, and the rest of the frame is left empty
 *  on purpose. */
export const TelaFinal: React.FC<P> = ({ o, dur, brand }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { x, height, width } = useMargem();
  const cor = accentOf(o.accent ?? brand?.color ?? "red");
  const op = fadeBorda(frame, dur, 16, 10);
  const p = pop(frame, 4, fps, 14, 165);
  const linha = prog(frame, 14, 20, easeOut);
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <AbsoluteFill style={{ background: `linear-gradient(90deg, rgba(5,5,8,0.9) 0%, rgba(5,5,8,0.62) 34%, rgba(5,5,8,0) 58%)` }} />
      <div
        style={{
          position: "absolute",
          left: x,
          top: height * 0.3,
          maxWidth: width * 0.34,
          transform: `translateY(${((1 - p) * 26).toFixed(1)}px)`,
          filter: SOMBRA,
        }}
      >
        {brand?.logo ? (
          <Img src={staticFile(brand.logo)} style={{ height: height * 0.11, objectFit: "contain", marginBottom: height * 0.028 }} />
        ) : null}
        <div style={{ ...tipoTitulo(height * 0.062), fontWeight: 700, textTransform: "uppercase", letterSpacing: 1.5 }}>
          {o.title ?? brand?.name}
        </div>
        <div
          style={{
            height: height * 0.006,
            width: "72%",
            marginTop: height * 0.022,
            background: `linear-gradient(90deg, ${cor}, ${rgba(cor, 0)})`,
            transform: `scaleX(${linha.toFixed(3)})`,
            transformOrigin: "0 50%",
          }}
        />
        <div style={{ ...tipoCorpo(height * 0.034), marginTop: height * 0.026, letterSpacing: 2 }}>
          {o.cta ?? "Inscreva-se"}
          {o.sub ? ` · ${o.sub}` : ""}
        </div>
      </div>
    </AbsoluteFill>
  );
};
