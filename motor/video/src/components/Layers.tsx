import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { clamp, easeInOut, easeOut, prog } from "../lib/anim";
import { FOG, accent as accentOf } from "../theme";
import type { Beat, FlashSpec, KF, LayerSpec, PKind, Scene } from "../types";
import { ArtPlate, type Box } from "./ArtPlate";
import { Flash, Fog, Particles } from "./fx";

export const toBox = (b: LayerSpec["box"], def: Box): Box => (b ? { left: b[0], top: b[1], width: b[2], height: b[3] } : def);

/** One art layer from the script, with its entrance (fade/emerge), dimming and glow flare. */
export const Layer: React.FC<{
  id: string;
  spec: LayerSpec;
  box: Box;
  camera: KF[];
  mask?: string;
  depth?: number;
  glowExtra?: number;
  imageMask?: string;
}> = ({ id, spec, box, camera, mask, depth = 12, glowExtra = 0, imageMask }) => {
  const frame = useCurrentFrame();
  const en = spec.enter;
  const brighten = en?.type === "brighten";
  const enterP = en ? prog(frame, en.f, en.dur ?? (en.type === "emerge" ? 120 : brighten ? 24 : 30), brighten ? easeOut : easeInOut) : 1;
  const emerge = en?.type === "emerge";
  const dimP = spec.dim ? prog(frame, spec.dim.f, spec.dim.dur ?? 30, easeInOut) : 0;
  const bright = (emerge ? 0.12 + 0.88 * enterP : brighten ? 0.3 + 0.7 * enterP : 1) * (1 - (spec.dim?.amount ?? 0.45) * dimP);
  const filters: string[] = [];
  if (emerge || brighten || spec.dim) filters.push(`brightness(${bright.toFixed(3)})`);
  if (emerge) filters.push(`blur(${((1 - enterP) * 10).toFixed(2)}px)`);
  if (spec.saturate !== undefined) filters.push(`saturate(${spec.saturate})`);
  const visible = emerge || brighten ? 1 : enterP;
  const flare = spec.flare ? (spec.flare.amount ?? 0.3) * (1 - prog(frame, spec.flare.f, spec.flare.dur ?? 60)) * visible : 0;
  return (
    <ArtPlate
      id={id}
      name={spec.art}
      box={box}
      kf={spec.camera ?? camera}
      mask={spec.mask ?? mask}
      imageMask={spec.imageMask ?? imageMask}
      depth={spec.depth ?? depth}
      glow={spec.glow ? { ...spec.glow, extra: flare + glowExtra } : undefined}
      flicker={spec.flicker}
      filter={filters.join(" ")}
      opacity={(spec.opacity ?? 1) * visible}
    />
  );
};

/** Fog + particles: scene values override the kind's defaults (`particles: []` disables them). */
export const Atmosphere: React.FC<{
  scene: Scene;
  particles: [PKind, number, string?][];
  fog: { opacity: number; color?: string; speed?: number };
}> = ({ scene, particles, fog }) => {
  const f = { ...fog, ...(scene.fog ?? {}) };
  const ps: [PKind, number, string?][] = scene.particles ? scene.particles.map((p) => [p.kind, p.count, p.color]) : particles;
  return (
    <>
      {f.opacity > 0 ? <Fog color={f.color ?? FOG[scene.accent] ?? accentOf(scene.accent)} opacity={f.opacity} speed={f.speed} seed={scene.image} /> : null}
      {ps.map(([k, n, col], i) => (
        <Particles key={i} kind={k} count={n} seed={`${scene.id}-${k}`} color={col} />
      ))}
    </>
  );
};

// ------------------------------------------------------------------ beats (script-driven hits)
export const beatImpacts = (scene: Scene) => (scene.beats ?? []).filter((b) => b.shake).map((b) => b.f);

export function beatGlow(scene: Scene, frame: number): number {
  let g = 0;
  for (const b of scene.beats ?? []) {
    if (!b.glow) continue;
    const [pre, peak, end, hold] = b.glowShape ?? [2, 3, 40, 0];
    const xs = [b.f - pre, b.f + Math.max(peak, 1 - pre), b.f + Math.max(end, peak + 1)];
    g += b.glow * interpolate(frame, xs, [0, 1, hold], clamp);
  }
  return g;
}

export const BeatFlashes: React.FC<{ scene: Scene }> = ({ scene }) => (
  <>
    {(scene.beats ?? [])
      .filter((b): b is Beat & { flash: true | FlashSpec } => Boolean(b.flash))
      .map((b, i) => {
        const fl: FlashSpec = typeof b.flash === "object" ? b.flash : {};
        return <Flash key={i} at={b.f} color={fl.color ?? accentOf(scene.accent)} dur={fl.dur ?? 22} peak={fl.peak ?? 0.3} cx={fl.cx} cy={fl.cy} />;
      })}
  </>
);

export const Darken: React.FC<{ css: string }> = ({ css }) => <AbsoluteFill style={{ background: css }} />;
