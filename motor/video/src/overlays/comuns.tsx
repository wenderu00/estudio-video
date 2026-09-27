import React from "react";
import { useVideoConfig } from "remotion";
import { prog } from "../lib/anim";
import { BARLOW, OSWALD, rgba } from "../theme";

/** Shared pieces of the video-mode overlays.
 *
 *  Everything is sized from the frame HEIGHT rather than in fixed pixels: the same overlay has to
 *  hold up on a 1080p screen capture and on a 4K camera, and the cut decides the output size. */

export const SOMBRA = "drop-shadow(0 10px 30px rgba(0,0,0,0.55))";
export const FUNDO = rgba("#07070A", 0.78);

/** In at the head, out at the tail — every overlay gets the same manners. */
export const fadeBorda = (frame: number, dur: number, entrada = 8, saida = 10) =>
  Math.min(prog(frame, 0, entrada), 1 - prog(frame, dur - saida, saida));

/** How much of the frame bottom the burned captions take, as a fraction of the height.
 *  Set once per render from the project's caption settings (montagem burns the .ass AFTER these
 *  overlays, so anything sitting in that band gets muddied by the caption's outline). */
let ZONA_LEGENDA = 0.22;
export const setZonaLegenda = (v?: number) => {
  if (typeof v === "number" && v >= 0 && v < 0.6) ZONA_LEGENDA = v;
};

/** Margin that keeps an overlay clear of the frame edge, of the player's chrome and of the
 *  caption band. `base` is where a lower third has to stop. */
export const useMargem = () => {
  const { width, height } = useVideoConfig();
  return {
    x: Math.round(width * 0.05),
    y: Math.round(height * 0.07),
    base: Math.round(height * (ZONA_LEGENDA + 0.02)),
    width,
    height,
  };
};

export const tipoTitulo = (px: number): React.CSSProperties => ({
  fontFamily: OSWALD,
  fontWeight: 600,
  fontSize: px,
  lineHeight: 1.1,
  letterSpacing: 0.5,
  color: "#FFFFFF",
});

export const tipoCorpo = (px: number): React.CSSProperties => ({
  fontFamily: BARLOW,
  fontWeight: 500,
  fontSize: px,
  lineHeight: 1.25,
  color: rgba("#FFFFFF", 0.84),
});

/** Dark panel with an accent edge — the shape the cartao, callout and card all share. */
export const Painel: React.FC<{
  cor: string;
  children: React.ReactNode;
  lado?: "left" | "top";
  espessura?: number;
  padding?: string;
}> = ({ cor, children, lado = "left", espessura = 10, padding = "18px 34px 20px 26px" }) => (
  <div style={{ display: "flex", flexDirection: lado === "left" ? "row" : "column", filter: SOMBRA }}>
    <div
      style={{
        background: cor,
        flex: "none",
        ...(lado === "left"
          ? { width: espessura, borderRadius: "3px 0 0 3px" }
          : { height: espessura, borderRadius: "3px 3px 0 0" }),
      }}
    />
    <div
      style={{
        background: FUNDO,
        padding,
        borderRadius: lado === "left" ? "0 6px 6px 0" : "0 0 6px 6px",
      }}
    >
      {children}
    </div>
  </div>
);
