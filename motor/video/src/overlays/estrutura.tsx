import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Icon } from "../components/icons";
import { easeOut, pop, prog } from "../lib/anim";
import { accent as accentOf, rgba } from "../theme";
import type { Overlay } from "../types";
import { FUNDO, Painel, SOMBRA, fadeBorda, tipoCorpo, tipoTitulo, useMargem } from "./comuns";

type P = { o: Overlay; dur: number };

/** Numbered chapter chip: flies in from the edge and parks in the upper corner. */
export const Secao: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { x, y, height } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const p = pop(frame, 0, fps, 13, 190);
  const op = fadeBorda(frame, dur, 6, 12);
  const direita = o.position === "right";
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: y,
          ...(direita ? { right: x } : { left: x }),
          display: "flex",
          alignItems: "stretch",
          opacity: op,
          transform: `translateX(${((1 - p) * (direita ? 80 : -80)).toFixed(1)}px)`,
          filter: SOMBRA,
        }}
      >
        {o.n ? (
          <div
            style={{
              background: cor,
              color: "#0B0B10",
              ...tipoTitulo(height * 0.05),
              fontWeight: 700,
              letterSpacing: -1,
              display: "flex",
              alignItems: "center",
              padding: `0 ${height * 0.022}px`,
            }}
          >
            {o.n}
          </div>
        ) : null}
        <div
          style={{
            background: FUNDO,
            ...tipoTitulo(height * 0.038),
            textTransform: "uppercase",
            letterSpacing: 1.5,
            display: "flex",
            alignItems: "center",
            padding: `${height * 0.016}px ${height * 0.032}px`,
          }}
        >
          {o.title}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Lower third: who is talking and what they do. */
export const Tarja: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { x, height, base } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const op = fadeBorda(frame, dur, 10, 12);
  const barra = prog(frame, 0, 12, easeOut);
  const nome = prog(frame, 6, 16, easeOut);
  const cargo = prog(frame, 12, 16, easeOut);
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div style={{ position: "absolute", left: x, bottom: base, display: "flex", filter: SOMBRA }}>
        <div style={{ width: height * 0.009, background: cor, transformOrigin: "50% 100%", transform: `scaleY(${barra.toFixed(3)})` }} />
        <div style={{ background: FUNDO, padding: `${height * 0.02}px ${height * 0.04}px ${height * 0.022}px ${height * 0.028}px` }}>
          <div
            style={{
              ...tipoTitulo(height * 0.055),
              fontWeight: 700,
              clipPath: `inset(-20% ${((1 - nome) * 100).toFixed(1)}% -20% 0)`,
            }}
          >
            {o.name ?? o.title}
          </div>
          {o.role ? (
            <div
              style={{
                ...tipoCorpo(height * 0.03),
                marginTop: height * 0.008,
                letterSpacing: 2,
                textTransform: "uppercase",
                color: rgba(cor, 0.95),
                clipPath: `inset(-20% ${((1 - cargo) * 100).toFixed(1)}% -20% 0)`,
              }}
            >
              {o.role}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Floating note with an icon: a term being named, a warning, an aside. */
export const Callout: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { x, y, height, width } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const p = pop(frame, 0, fps, 12, 180);
  const op = fadeBorda(frame, dur);
  const esquerda = o.position === "left";
  const ic = height * 0.062;
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div
        style={{
          position: "absolute",
          top: y * 1.6,
          ...(esquerda ? { left: x } : { right: x }),
          maxWidth: width * 0.34,
          transform: `translateY(${((1 - p) * -26).toFixed(1)}px) scale(${(0.94 + 0.06 * p).toFixed(3)})`,
        }}
      >
        <Painel cor={cor} padding={`${height * 0.022}px ${height * 0.032}px`}>
          <div style={{ display: "flex", alignItems: "center", gap: height * 0.022 }}>
            <div style={{ flex: "none", filter: `drop-shadow(0 0 ${height * 0.012}px ${rgba(cor, 0.6)})` }}>
              <Icon name={o.icon ?? "Info"} size={ic} color={cor} />
            </div>
            <div>
              <div style={tipoTitulo(height * 0.04)}>{o.title}</div>
              {o.sub ? <div style={{ ...tipoCorpo(height * 0.027), marginTop: height * 0.006 }}>{o.sub}</div> : null}
            </div>
          </div>
        </Painel>
      </div>
    </AbsoluteFill>
  );
};

/** A list the viewer needs to read: title plus items that arrive one at a time. */
export const Card: React.FC<P> = ({ o, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { height, width } = useMargem();
  const cor = accentOf(o.accent ?? "red");
  const p = pop(frame, 0, fps, 14, 170);
  const op = fadeBorda(frame, dur, 8, 12);
  const itens = o.items ?? [];
  const meio = o.position === "center" || !o.position;
  return (
    <AbsoluteFill style={{ opacity: op, justifyContent: "center", alignItems: meio ? "center" : "flex-start" }}>
      <div
        style={{
          maxWidth: width * 0.56,
          marginLeft: meio ? 0 : width * 0.06,
          transform: `translateY(${((1 - p) * 22).toFixed(1)}px) scale(${(0.96 + 0.04 * p).toFixed(3)})`,
        }}
      >
        <Painel cor={cor} lado="top" espessura={Math.round(height * 0.008)} padding={`${height * 0.034}px ${height * 0.046}px`}>
          <div style={{ ...tipoTitulo(height * 0.055), fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
            {o.title}
          </div>
          {itens.map((it, i) => {
            const a = prog(frame, 10 + i * 9, 14, easeOut);
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: height * 0.02,
                  marginTop: height * (i === 0 ? 0.028 : 0.02),
                  opacity: a,
                  transform: `translateX(${((1 - a) * -18).toFixed(1)}px)`,
                }}
              >
                <div style={{ width: height * 0.012, height: height * 0.012, background: cor, flex: "none", transform: "rotate(45deg)" }} />
                <div style={tipoCorpo(height * 0.036)}>{it}</div>
              </div>
            );
          })}
        </Painel>
      </div>
    </AbsoluteFill>
  );
};
