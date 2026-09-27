import React from "react";
import { Easing, Img, staticFile, useCurrentFrame } from "remotion";
import { noise2D } from "@remotion/noise";
import { DEPTH, artInfo } from "../lib/assets";
import type { KF } from "../types";

export type { KF };

export type Box = { left: number; top: number; width: number; height: number };

const ease = Easing.inOut(Easing.sin);

export function kfAt(kf: KF[], frame: number): KF {
  if (frame <= kf[0].f) return kf[0];
  for (let i = 0; i < kf.length - 1; i++) {
    const a = kf[i];
    const b = kf[i + 1];
    if (frame <= b.f) {
      const p = ease((frame - a.f) / Math.max(1, b.f - a.f));
      return { f: frame, s: a.s + (b.s - a.s) * p, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p };
    }
  }
  return kf[kf.length - 1];
}

type Props = {
  id: string;
  name: string;
  box: Box;
  kf: KF[];
  mask?: string;
  imageMask?: string;
  depth?: number; // max parallax displacement in px (0 disables)
  glow?: { base: number; amp: number; period: number; extra?: number };
  flicker?: number;
  filter?: string;
  opacity?: number;
  style?: React.CSSProperties;
};

export const ArtPlate: React.FC<Props> = ({ id, name, box, kf, mask, imageMask, depth = 0, glow, flicker = 0, filter = "", opacity = 1, style }) => {
  const frame = useCurrentFrame();
  const { w, h } = artInfo(name);
  const cover = Math.max(box.width / w, box.height / h);
  const W0 = w * cover;
  const H0 = h * cover;
  const cam = kfAt(kf, frame);
  const k = cam.s;
  const ox = (-cam.x * (W0 * k - box.width)) / 2;
  const oy = (-cam.y * (H0 * k - box.height)) / 2;
  const tx = box.width / 2 - (W0 * k) / 2 + ox;
  const ty = box.height / 2 - (H0 * k) / 2 + oy;

  // Parallax: position along the camera's travel on each axis (-1 at the start, +1 at the end).
  // Near pixels (depth=1) shift against the camera more than far ones. Zoom-only moves sway slightly.
  const first = kf[0];
  const last = kf[kf.length - 1];
  const rx = (last.x - first.x) / 2;
  const ry = (last.y - first.y) / 2;
  const rs = (last.s - first.s) / 2;
  const c1 = (v: number) => Math.max(-1, Math.min(1, v));
  const px = Math.abs(rx) > 1e-3 ? c1((cam.x - (first.x + rx)) / rx) : 0;
  const py = Math.abs(ry) > 1e-3 ? c1((cam.y - (first.y + ry)) / ry) : 0;
  const ps = Math.abs(rs) > 1e-3 ? c1((cam.s - (first.s + rs)) / rs) : 0;
  const dX = depth * (Math.abs(rx) > 1e-3 ? px * Math.sign(rx) * Math.min(1, Math.abs(rx) * 3) : ps * 0.6);
  const dY = depth * (Math.abs(ry) > 1e-3 ? py * Math.sign(ry) * Math.min(1, Math.abs(ry) * 3) : ps * 0.3);
  const useDepth = depth > 0 && DEPTH[name];
  const fid = `depth-${id}`;

  const flk = flicker ? 1 + flicker * noise2D(`flk-${id}`, frame * 0.18, 0) : 1;
  const glowOp = glow ? Math.max(0, glow.base + glow.amp * Math.sin((frame / glow.period) * Math.PI * 2) + (glow.extra ?? 0)) : 0;

  const maskStyle: React.CSSProperties = mask
    ? { WebkitMaskImage: mask, maskImage: mask, WebkitMaskComposite: mask.includes("),") ? "source-in" : undefined, maskComposite: mask.includes("),") ? "intersect" : undefined }
    : {};
  const imgMaskStyle: React.CSSProperties = imageMask ? { WebkitMaskImage: imageMask, maskImage: imageMask } : {};
  const layer: React.CSSProperties = {
    position: "absolute",
    left: 0,
    top: 0,
    width: W0,
    height: H0,
    transformOrigin: "0 0",
    transform: `translate(${tx.toFixed(3)}px, ${ty.toFixed(3)}px) scale(${k.toFixed(5)})`,
  };

  return (
    <div
      style={{
        position: "absolute",
        ...box,
        overflow: "hidden",
        opacity,
        filter: `${flicker ? `brightness(${flk.toFixed(3)})` : ""} ${filter}`.trim() || undefined,
        ...maskStyle,
        ...style,
      }}
    >
      {useDepth ? (
        <svg width={0} height={0} style={{ position: "absolute" }} aria-hidden>
          <defs>
            <filter id={fid} x={0} y={0} width={W0} height={H0} filterUnits="userSpaceOnUse" primitiveUnits="userSpaceOnUse" colorInterpolationFilters="sRGB">
              <feImage href={DEPTH[name]} x={0} y={0} width={W0} height={H0} preserveAspectRatio="none" result="d" />
              <feDisplacementMap in="SourceGraphic" in2="d" scale={dX.toFixed(2)} xChannelSelector="R" yChannelSelector="B" result="dx" />
              <feDisplacementMap in="dx" in2="d" scale={dY.toFixed(2)} xChannelSelector="B" yChannelSelector="G" />
            </filter>
          </defs>
        </svg>
      ) : null}
      <div style={{ ...layer, ...imgMaskStyle }}>
        <Img
          src={staticFile(`art/${name}.jpg`)}
          style={{ width: W0, height: H0, display: "block", filter: useDepth ? `url(#${fid})` : undefined }}
        />
        {glow ? (
          <Img
            src={staticFile(`art/${name}_glow.jpg`)}
            style={{ position: "absolute", left: 0, top: 0, width: W0, height: H0, mixBlendMode: "screen", opacity: Math.min(1, glowOp) }}
          />
        ) : null}
      </div>
    </div>
  );
};
