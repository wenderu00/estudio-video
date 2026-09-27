import React, { useMemo } from "react";
import { AbsoluteFill, Easing, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeInOut, easeOut, prog } from "../lib/anim";
import { FOG, accent as accentOf, rgb } from "../theme";
import type { Scene } from "../types";
import { Flash } from "./fx";

export const OVERLAP = new Set(["splatter", "fog", "drip", "slash", "whip", "zoomBlur", "crossfade"]);

type Exit = { type: string; frames: number } | null;

const setMask = (st: React.CSSProperties, img: string, size: string, pos: string) => {
  Object.assign(st, {
    WebkitMaskImage: img,
    maskImage: img,
    WebkitMaskSize: size,
    maskSize: size,
    WebkitMaskPosition: pos,
    maskPosition: pos,
    WebkitMaskRepeat: "no-repeat",
    maskRepeat: "no-repeat",
  });
};

const SPLATS = [
  { x: 0.3, y: 0.44, k: 0, d: 0, s: 5.2 },
  { x: 0.76, y: 0.3, k: 1, d: 2, s: 2.4 },
  { x: 0.62, y: 0.84, k: 2, d: 4, s: 2.2 },
  { x: 0.1, y: 0.12, k: 3, d: 6, s: 1.9 },
  { x: 0.92, y: 0.78, k: 4, d: 7, s: 1.9 },
];

export const SceneShell: React.FC<{ scene: Scene; exit: Exit; children: React.ReactNode }> = ({ scene, exit, children }) => {
  const frame = useCurrentFrame();
  const { width: W, height: H } = useVideoConfig();
  const tin = scene.transitionIn;
  const N = Math.max(1, tin.frames);
  const p = interpolate(frame, [0, N], [0, 1], clamp);
  const accent = accentOf(scene.accent);
  const dripColor = `rgb(${rgb(accent).split(",").map((v) => Math.round(Number(v) * 0.46)).join(",")})`;
  const content: React.CSSProperties = {};
  const transforms: string[] = [];
  const filters: string[] = [];
  let under: React.ReactNode = null;
  let over: React.ReactNode = null;

  const drips = useMemo(
    () =>
      Array.from({ length: 17 }, (_, i) => ({
        x: ((i + 0.5) / 17) * W + (random(`dx${i}`) - 0.5) * (W / 22),
        w: 16 + random(`dw${i}`) * 46,
        L: 0.06 * H + random(`dl${i}`) * 0.26 * H,
      })).sort((a, b) => b.x - a.x),
    [W, H],
  );

  if (frame <= N) {
    switch (tin.type) {
      case "fadeFromBlack":
      case "crossfade":
        content.opacity = easeInOut(p);
        break;
      case "splatter": {
        const base = Math.max(W, H);
        const mk = (mult: number) => {
          const ls = SPLATS.map((b) => {
            const g = prog(frame, b.d, N - b.d, Easing.bezier(0.45, 0.05, 0.55, 0.95));
            const size = Math.max(1, base * b.s * g * mult);
            return { url: `url(${staticFile(`fx/splatter_${b.k}.png`)})`, size, x: b.x * W - size / 2, y: b.y * H - size / 2 };
          });
          return [
            ls.map((l) => l.url).join(", "),
            ls.map((l) => `${l.size.toFixed(1)}px ${l.size.toFixed(1)}px`).join(", "),
            ls.map((l) => `${l.x.toFixed(1)}px ${l.y.toFixed(1)}px`).join(", "),
          ] as const;
        };
        const [img, size, pos] = mk(1);
        setMask(content, img, size, pos);
        const ink: React.CSSProperties = { backgroundColor: accent, opacity: 1 - prog(frame, N * 0.6, N * 0.4) };
        const [img2, size2, pos2] = mk(1.16);
        setMask(ink, img2, size2, pos2);
        under = <AbsoluteFill style={ink} />;
        break;
      }
      case "fog": {
        content.opacity = easeInOut(p);
        filters.push(`blur(${((1 - p) * 12).toFixed(2)}px)`);
        transforms.push(`scale(${(1.05 - 0.05 * easeOut(p)).toFixed(4)})`);
        const url = `url(${staticFile("fx/fog_0.png")})`;
        const burst: React.CSSProperties = {
          backgroundColor: FOG[scene.accent] ?? accent,
          mixBlendMode: "screen",
          opacity: Math.sin(p * Math.PI) * 0.9,
          WebkitMaskImage: url,
          maskImage: url,
          WebkitMaskSize: "3600px 1800px",
          maskSize: "3600px 1800px",
          WebkitMaskPosition: `${(-frame * 14).toFixed(1)}px -300px`,
          maskPosition: `${(-frame * 14).toFixed(1)}px -300px`,
        };
        over = <AbsoluteFill style={burst} />;
        break;
      }
      case "drip": {
        const y = interpolate(p, [0, 1], [-0.3 * H, 1.35 * H], { ...clamp, easing: easeInOut });
        const grow = 0.35 + 0.65 * p;
        const edge = (dy: number, dw: number) => {
          let d = `M 0 0 H ${W} V ${(y + dy).toFixed(1)} `;
          for (const dr of drips) {
            const w = dr.w + dw;
            const L = dr.L * grow + dy;
            const xr = dr.x + w / 2;
            const xl = dr.x - w / 2;
            const yb = y + L;
            d += `L ${xr.toFixed(1)} ${(y + dy + 8 * Math.sin(xr / 70)).toFixed(1)} L ${xr.toFixed(1)} ${(yb - w / 2).toFixed(1)} A ${(w / 2).toFixed(1)} ${(w / 2).toFixed(1)} 0 0 1 ${xl.toFixed(1)} ${(yb - w / 2).toFixed(1)} L ${xl.toFixed(1)} ${(y + dy + 8 * Math.sin(xl / 70)).toFixed(1)} `;
          }
          d += `L 0 ${(y + dy).toFixed(1)} Z`;
          return d;
        };
        content.clipPath = `path('${edge(0, 0)}')`;
        under = <AbsoluteFill style={{ backgroundColor: dripColor, clipPath: `path('${edge(22, 10)}')` }} />;
        break;
      }
      case "slash": {
        const ang = (-16 * Math.PI) / 180;
        const ux = Math.cos(ang);
        const uy = Math.sin(ang);
        const nx = -uy;
        const ny = ux;
        const Lh = Math.hypot(W, H);
        const half = interpolate(p, [0, 1], [2, Lh * 0.62], { ...clamp, easing: Easing.bezier(0.7, 0, 0.3, 1) });
        const cx = W / 2;
        const cy = H / 2;
        const pt = (a: number, b: number) => `${(cx + ux * a + nx * b).toFixed(1)}px ${(cy + uy * a + ny * b).toFixed(1)}px`;
        content.clipPath = `polygon(${pt(-Lh, -half)}, ${pt(Lh, -half)}, ${pt(Lh, half)}, ${pt(-Lh, half)})`;
        over = (
          <>
            <AbsoluteFill style={{ pointerEvents: "none" }}>
              <div
                style={{
                  position: "absolute",
                  left: cx - Lh,
                  top: cy - 3,
                  width: Lh * 2,
                  height: 6 + 30 * (1 - p),
                  marginTop: -(15 * (1 - p)),
                  background: "linear-gradient(90deg, rgba(255,255,255,0), rgba(235,245,255,0.95) 50%, rgba(255,255,255,0))",
                  transform: `rotate(${-16}deg)`,
                  opacity: 1 - p,
                  filter: "blur(2px)",
                }}
              />
            </AbsoluteFill>
            <Flash at={1} color="200,225,255" dur={14} peak={0.45} />
          </>
        );
        break;
      }
      case "whip":
        transforms.push(`translateX(${((1 - easeOut(p)) * W * 0.95).toFixed(1)}px)`);
        filters.push(`blur(${((1 - p) * 22).toFixed(2)}px)`);
        break;
      case "zoomBlur":
        content.opacity = prog(frame, 0, N * 0.55);
        transforms.push(`scale(${(1.3 - 0.3 * easeOut(p)).toFixed(4)})`);
        filters.push(`blur(${((1 - p) * 16).toFixed(2)}px)`);
        over = <Flash at={0} color="200,160,255" dur={N} peak={0.8} />;
        break;
      default:
        break;
    }
  }

  // complementary exit, driven by the next scene's entrance
  if (exit) {
    const M = Math.max(1, exit.frames);
    const q = interpolate(frame, [scene.durFrames - M, scene.durFrames], [0, 1], clamp);
    if (q > 0) {
      if (exit.type === "zoomBlur") {
        transforms.push(`scale(${(1 + 0.35 * q * q).toFixed(4)})`);
        filters.push(`blur(${(q * 14).toFixed(2)}px)`);
      } else if (exit.type === "whip") {
        transforms.push(`translateX(${(-q * q * W * 0.5).toFixed(1)}px)`);
        filters.push(`blur(${(q * 18).toFixed(2)}px)`);
      } else if (exit.type === "fog" || exit.type === "crossfade") {
        filters.push(`blur(${(q * 5).toFixed(2)}px)`);
      }
    }
  }
  if (transforms.length) content.transform = transforms.join(" ");
  if (filters.length) content.filter = filters.join(" ");

  let black = 0;
  const tout = scene.transitionOut;
  if (tout?.type === "fadeBlack") black = interpolate(frame, [scene.durFrames - tout.frames, scene.durFrames - 6], [0, 1], clamp);
  if (tout?.type === "cutBlack") black = frame >= scene.durFrames - tout.holdFrames ? 1 : 0;

  return (
    <AbsoluteFill>
      {under}
      <AbsoluteFill style={content}>{children}</AbsoluteFill>
      {over}
      {black > 0 ? <AbsoluteFill style={{ backgroundColor: "#000", opacity: black }} /> : null}
    </AbsoluteFill>
  );
};
