import { Easing, interpolate, spring } from "remotion";
import { noise2D } from "@remotion/noise";
import type { Line, Scene } from "../types";

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const easeOut = Easing.bezier(0.22, 1, 0.36, 1);
export const easeInOut = Easing.bezier(0.65, 0, 0.35, 1);

/** 0→1 progress between start and start+dur (frames). */
export const prog = (frame: number, start: number, dur: number, easing = easeOut) =>
  interpolate(frame, [start, start + Math.max(1, dur)], [0, 1], { ...clamp, easing });

export const pop = (frame: number, start: number, fps: number, damping = 13, stiffness = 170) =>
  frame < start ? 0 : spring({ frame: frame - start, fps, config: { damping, stiffness, mass: 0.9 } });

export const lineOf = (scene: Scene, screen: string) => scene.lines.find((l) => l.screen === screen);
export const linesOf = (scene: Scene, prefix: string) => scene.lines.filter((l) => l.screen.startsWith(prefix));

export const norm = (s: string) =>
  s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]/g, "");

/** Map on-screen tokens to spoken word timings (frames relative to the scene). */
export function syncTokens(screenText: string, line: Line) {
  const toks = screenText.split(/\s+/).filter(Boolean);
  const words = line.words;
  let j = 0;
  let last = line.rel;
  return toks.map((tok) => {
    const n = norm(tok);
    let found = -1;
    for (let k = j; k < Math.min(words.length, j + 4); k++) {
      if (norm(words[k].w) === n || (n.length > 3 && norm(words[k].w).startsWith(n.slice(0, 4)))) {
        found = k;
        break;
      }
    }
    if (found >= 0) {
      last = words[found].rel;
      j = found + 1;
    } else if (n !== "") {
      last += 2;
    }
    return { tok, rel: last };
  });
}

/** Highlight rule from the script: `hl` words and/or everything from `hlFrom` on. */
export function highlighter(line: Line | undefined, color: string) {
  if (!line) return undefined;
  const set = new Set((line.hl ?? []).map(norm));
  const from = line.hlFrom ? norm(line.hlFrom) : null;
  if (!set.size && !from) return undefined;
  const toks = line.screenText.split(/\s+/).filter(Boolean);
  const start = from ? toks.findIndex((t) => norm(t) === from) : -1;
  return (tok: string, i: number) => ((start >= 0 && i >= start) || set.has(norm(tok)) ? color : undefined);
}

/** Decaying camera shake from impact frames. */
export function shake(frame: number, impacts: number[], amp = 12, decay = 9) {
  let x = 0;
  let y = 0;
  let r = 0;
  for (const f0 of impacts) {
    const d = frame - f0;
    if (d < 0 || d > decay * 5) continue;
    const a = amp * Math.exp(-d / decay);
    x += a * noise2D("sx" + f0, d * 0.45, 0);
    y += a * noise2D("sy" + f0, d * 0.45, 1);
    r += a * 0.05 * noise2D("sr" + f0, d * 0.4, 2);
  }
  return `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px) rotate(${r.toFixed(3)}deg)`;
}

/** Gentle idle drift (handheld feel). */
export function drift(frame: number, seed: string, amp = 3) {
  const x = amp * noise2D(seed + "x", frame * 0.008, 0);
  const y = amp * noise2D(seed + "y", frame * 0.008, 1);
  return `translate(${x.toFixed(2)}px, ${y.toFixed(2)}px)`;
}

/** Style knob from the scene with a default. */
export function knob<T extends number | string | boolean>(scene: Scene, key: string, def: T): T {
  const v = scene.style?.[key];
  return (v === undefined ? def : v) as T;
}
