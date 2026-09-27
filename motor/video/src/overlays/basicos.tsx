import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { easeOut, pop, prog } from "../lib/anim";
import { accent as accentOf, rgba } from "../theme";
import type { Overlay } from "../types";
import { Painel, SOMBRA, fadeBorda, tipoCorpo, tipoTitulo, useMargem } from "./comuns";

type P = { o: Overlay; dur: number };

/** Lower third for a concept being named. */
export const Cartao: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { x, height, width, base } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const p = prog(frame, 0, 18, easeOut);
  const op = fadeBorda(frame, dur);
  const direita = o.position === "right";
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div
        style={{
          position: "absolute",
          bottom: base,
          ...(direita ? { right: x } : { left: x }),
          maxWidth: width * 0.46,
          transform: `translateX(${((1 - p) * (direita ? 60 : -60)).toFixed(1)}px)`,
        }}
      >
        <Painel cor={cor} espessura={Math.round(height * 0.009)} padding={`${height * 0.018}px ${height * 0.032}px ${height * 0.02}px ${height * 0.024}px`}>
          <div style={{ ...tipoTitulo(height * 0.05), fontWeight: 600 }}>{o.title}</div>
          {o.sub ? <div style={{ ...tipoCorpo(height * 0.028), marginTop: height * 0.008 }}>{o.sub}</div> : null}
        </Painel>
      </div>
    </AbsoluteFill>
  );
};

/** Full-screen title card. */
export const Titulo: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { height, width } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const p = pop(frame, 0, fps, 13, 180);
  const op = fadeBorda(frame, dur, 10, 12);
  const linha = prog(frame, 8, 18, easeOut);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: op }}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse 70% 60% at 50% 50%, rgba(5,5,8,0.82) 0%, rgba(5,5,8,0.35) 60%, rgba(5,5,8,0) 100%)` }} />
      <div style={{ textAlign: "center", padding: `0 ${width * 0.08}px`, transform: `scale(${(0.93 + 0.07 * p).toFixed(3)})`, filter: SOMBRA }}>
        <div style={{ ...tipoTitulo(height * 0.095), fontWeight: 700, textTransform: "uppercase", letterSpacing: 2 }}>{o.title}</div>
        <div
          style={{
            height: height * 0.008,
            width: `${(30 + linha * 40).toFixed(1)}%`,
            background: cor,
            margin: `${height * 0.024}px auto 0`,
            borderRadius: height * 0.004,
          }}
        />
        {o.sub ? <div style={{ ...tipoCorpo(height * 0.036), marginTop: height * 0.02 }}>{o.sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

/** Attention on one region: corner brackets plus a dimming of everything around it.
 *  The dim is what actually moves the eye — a bare rectangle competes with the picture. */
export const Destaque: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { width, height, base } = useMargem();
  const [bx, by, bw, bh] = o.box ?? [0.1, 0.1, 0.35, 0.3];
  const cor = accentOf(o.accent ?? "red");
  const p = prog(frame, 0, 14, easeOut);
  const op = fadeBorda(frame, dur);
  const L = bx * width;
  const T = by * height;
  const W = bw * width;
  const H = bh * height;
  const esc = Math.round(Math.min(W, H) * 0.22); // bracket arm
  const g = Math.max(3, Math.round(height * 0.005));
  const escurecer = 0.42 * p;
  const canto = (dx: number, dy: number): React.CSSProperties => ({
    position: "absolute",
    width: esc,
    height: esc,
    borderTop: dy < 0 ? `${g}px solid ${cor}` : undefined,
    borderBottom: dy > 0 ? `${g}px solid ${cor}` : undefined,
    borderLeft: dx < 0 ? `${g}px solid ${cor}` : undefined,
    borderRight: dx > 0 ? `${g}px solid ${cor}` : undefined,
    left: dx < 0 ? -g : undefined,
    right: dx > 0 ? -g : undefined,
    top: dy < 0 ? -g : undefined,
    bottom: dy > 0 ? -g : undefined,
    filter: `drop-shadow(0 0 ${height * 0.012}px ${rgba(cor, 0.5)})`,
  });
  const fora: React.CSSProperties = { position: "absolute", background: `rgba(4,4,7,${escurecer.toFixed(3)})` };
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div style={{ ...fora, left: 0, top: 0, width, height: T }} />
      <div style={{ ...fora, left: 0, top: T + H, width, height: Math.max(0, height - T - H) }} />
      <div style={{ ...fora, left: 0, top: T, width: L, height: H }} />
      <div style={{ ...fora, left: L + W, top: T, width: Math.max(0, width - L - W), height: H }} />
      <div style={{ position: "absolute", left: L, top: T, width: W, height: H, transform: `scale(${(0.97 + 0.03 * p).toFixed(3)})` }}>
        <div style={canto(-1, -1)} />
        <div style={canto(1, -1)} />
        <div style={canto(-1, 1)} />
        <div style={canto(1, 1)} />
      </div>
      {o.title ? (
        <div
          style={{
            position: "absolute",
            left: L,
            // below the box, unless that would drop the label into the caption band
            ...(T + H + height * 0.07 > height - base
              ? { bottom: height - T + height * 0.014 }
              : { top: T + H + height * 0.014 }),
            background: cor,
            color: "#0B0B10",
            ...tipoTitulo(height * 0.032),
            fontWeight: 700,
            padding: `${height * 0.006}px ${height * 0.016}px`,
            opacity: prog(frame, 8, 12),
            filter: SOMBRA,
          }}
        >
          {o.title}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

/** A picture over the talk: b-roll, a screenshot, a diagram.
 *
 *  It drifts and scales slowly (a Ken Burns move) — a still rectangle dropped on moving footage
 *  reads as a bug. */
export const Imagem: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const [bx, by, bw, bh] = o.box ?? [0.56, 0.08, 0.38, 0.38];
  const p = prog(frame, 0, 16, easeOut);
  const op = fadeBorda(frame, dur);
  const cheia = bw >= 0.98 && bh >= 0.98;
  const t = Math.min(1, frame / Math.max(1, dur));
  const zoom = 1.04 + 0.05 * t; // slow push, always covering the box
  const desloc = (t - 0.5) * 0.9;
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div
        style={{
          position: "absolute",
          left: bx * width,
          top: by * height,
          width: bw * width,
          height: bh * height,
          transform: `translateY(${((1 - p) * 18).toFixed(1)}px)`,
          overflow: "hidden",
          borderRadius: cheia ? 0 : Math.round(height * 0.008),
          boxShadow: cheia ? "none" : `0 ${height * 0.016}px ${height * 0.046}px rgba(0,0,0,0.6)`,
          border: cheia ? "none" : `${Math.max(2, Math.round(height * 0.003))}px solid ${rgba("#FFFFFF", 0.85)}`,
        }}
      >
        <Img
          src={staticFile(o.file as string)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${zoom.toFixed(4)}) translate(${(desloc * 1.2).toFixed(2)}%, ${(desloc * 0.8).toFixed(2)}%)`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
