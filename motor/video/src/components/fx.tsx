import React, { useMemo } from "react";
import { AbsoluteFill, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { rgb } from "../theme";
import type { PKind } from "../types";

// ------------------------------------------------------------------ particles
export type { PKind };

type PProps = {
  kind: PKind;
  count: number;
  seed: string;
  color?: string;
  opacity?: number;
  speed?: number;
  size?: number;
  area?: { left: number; top: number; width: number; height: number };
};

export const Particles: React.FC<PProps> = ({ kind, count, seed, color, opacity = 1, speed = 1, size = 1, area }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const A = area ?? { left: 0, top: 0, width, height };
  const ps = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const r = (k: string) => random(`${seed}-${k}-${i}`);
        return { x: r("x"), y: r("y"), v: 0.5 + r("v"), s: 0.45 + r("s") * 0.9, ph: r("p") * Math.PI * 2, w: 0.5 + r("w"), rot: r("r") * 360, z: r("z") };
      }),
    [count, seed],
  );
  const blend = kind === "ash" || kind === "petals" ? "normal" : "screen";
  return (
    <div style={{ position: "absolute", ...A, overflow: "hidden", pointerEvents: "none", mixBlendMode: blend, opacity }}>
      {ps.map((p, i) => {
        const H = A.height + 80;
        const Wd = A.width + 80;
        let x = 0;
        let y = 0;
        let el: React.CSSProperties = {};
        let op = 1;
        if (kind === "embers" || kind === "sparks") {
          const sp = (kind === "embers" ? 1.5 : 2.1) * p.v * speed * (0.6 + p.z);
          y = ((((p.y * H - frame * sp) % H) + H) % H) - 40;
          x = ((p.x * Wd + Math.sin(frame * 0.035 * p.w + p.ph) * 28 + frame * 0.25 * (p.w - 1)) % Wd + Wd) % Wd - 40;
          const d = (kind === "embers" ? 5 : 3.2) * p.s * size * (0.6 + p.z);
          op = 0.35 + 0.65 * Math.abs(Math.sin(frame * (kind === "embers" ? 0.12 : 0.3) * p.w + p.ph));
          const c = color ?? (kind === "embers" ? "255,120,60" : "190,140,255");
          el = {
            width: d * 4,
            height: d * 4,
            marginLeft: -d * 2,
            marginTop: -d * 2,
            background: `radial-gradient(circle, rgba(${c},1) 0%, rgba(${c},0.55) 18%, rgba(${c},0) 60%)`,
          };
        } else if (kind === "ash") {
          const sp = 0.8 * p.v * speed;
          y = ((((p.y * H + frame * sp) % H) + H) % H) - 40;
          x = ((p.x * Wd + Math.sin(frame * 0.02 * p.w + p.ph) * 40 - frame * 0.35) % Wd + Wd) % Wd - 40;
          const d = 3 + 4 * p.s * size;
          op = 0.25 + 0.45 * p.z;
          el = { width: d, height: d * 0.7, background: color ?? "#9a938c", borderRadius: "35%", transform: `rotate(${p.rot + frame * 2 * p.w}deg)` };
        } else if (kind === "dust") {
          y = (((p.y * H + Math.sin(frame * 0.01 * p.w + p.ph) * 30 - frame * 0.12 * p.v * speed) % H) + H) % H - 40;
          x = ((p.x * Wd + Math.cos(frame * 0.012 * p.w + p.ph) * 30) % Wd + Wd) % Wd - 40;
          const d = 1.6 + 2.4 * p.s * size;
          op = 0.15 + 0.5 * p.z * (0.6 + 0.4 * Math.sin(frame * 0.05 + p.ph));
          el = { width: d, height: d, borderRadius: "50%", background: color ?? "#f2ece2", boxShadow: `0 0 ${d * 2}px ${color ?? "#f2ece2"}` };
        } else {
          // petals
          const sp = 1.1 * p.v * speed;
          y = ((((p.y * H + frame * sp) % H) + H) % H) - 40;
          x = ((p.x * Wd + Math.sin(frame * 0.025 * p.w + p.ph) * 60 - frame * 0.5) % Wd + Wd) % Wd - 40;
          const d = (9 + 7 * p.s) * size;
          op = 0.55 + 0.4 * p.z;
          const flip = Math.cos(frame * 0.06 * p.w + p.ph);
          el = {
            width: d,
            height: d * 0.62,
            borderRadius: "70% 10% 70% 10%",
            background: color ?? "linear-gradient(135deg, #7a1022, #3a0610)",
            transform: `rotate(${p.rot + frame * 1.6 * p.w}deg) scaleX(${flip.toFixed(3)})`,
          };
        }
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              translate: `${x.toFixed(1)}px ${y.toFixed(1)}px`,
              opacity: op,
              ...el,
            }}
          />
        );
      })}
    </div>
  );
};

// ------------------------------------------------------------------ fog
export const Fog: React.FC<{ color: string; opacity: number; speed?: number; scale?: number; seed?: number; top?: number }> = ({
  color,
  opacity,
  speed = 0.6,
  scale = 1.2,
  seed = 0,
  top = 0,
}) => {
  const frame = useCurrentFrame();
  const layers = [
    { k: 0, sp: speed, sc: scale, op: 1, dy: 0 },
    { k: 1, sp: -speed * 0.6, sc: scale * 1.5, op: 0.7, dy: 120 },
  ];
  return (
    <AbsoluteFill style={{ pointerEvents: "none", top }}>
      {layers.map((l) => {
        const url = `url(${staticFile(`fx/fog_${l.k}.png`)})`;
        const size = `${(2048 * l.sc).toFixed(0)}px ${(1024 * l.sc).toFixed(0)}px`;
        const pos = `${(frame * l.sp + seed * 331).toFixed(1)}px ${(Math.sin(frame / 140 + seed) * 25 + l.dy).toFixed(1)}px`;
        return (
          <AbsoluteFill
            key={l.k}
            style={{
              backgroundColor: color,
              opacity: opacity * l.op,
              mixBlendMode: "screen",
              WebkitMaskImage: url,
              maskImage: url,
              WebkitMaskSize: size,
              maskSize: size,
              WebkitMaskPosition: pos,
              maskPosition: pos,
              WebkitMaskRepeat: "repeat",
              maskRepeat: "repeat",
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ overlays
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.085 }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        backgroundImage: `url(${staticFile(`fx/grain_${frame % 8}.png`)})`,
        backgroundSize: "100% 100%",
        mixBlendMode: "overlay",
        opacity,
        pointerEvents: "none",
      }}
    />
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.78 }) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(ellipse 75% 70% at 50% 46%, rgba(0,0,0,0) 50%, rgba(0,0,0,${strength}) 100%)`,
      pointerEvents: "none",
    }}
  />
);

export const Flash: React.FC<{ at: number; color?: string; dur?: number; peak?: number; cx?: string; cy?: string }> = ({
  at,
  color = "255,255,255",
  dur = 18,
  peak = 0.6,
  cx = "50%",
  cy = "50%",
}) => {
  const frame = useCurrentFrame();
  const d = frame - at;
  if (d < -3 || d > dur) return null;
  if (color.startsWith("#")) color = rgb(color);
  const op = d < 0 ? ((d + 3) / 3) * peak : peak * Math.exp((-d / dur) * 3.2);
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at ${cx} ${cy}, rgba(${color},1) 0%, rgba(${color},0.35) 35%, rgba(${color},0) 75%)`,
        mixBlendMode: "screen",
        opacity: op,
        pointerEvents: "none",
      }}
    />
  );
};

export const Backdrop: React.FC<{ image: number; opacity?: number; grunge?: number }> = ({ image, opacity = 0.55, grunge = 1 }) => (
  <AbsoluteFill style={{ backgroundColor: "#060608" }}>
    <AbsoluteFill style={{ backgroundImage: `url(${staticFile("fx/grunge.jpg")})`, backgroundSize: "cover", opacity: grunge }} />
    <AbsoluteFill
      style={{ backgroundImage: `url(${staticFile(`art/bg_${image}.jpg`)})`, backgroundSize: "cover", backgroundPosition: "center", opacity }}
    />
  </AbsoluteFill>
);
