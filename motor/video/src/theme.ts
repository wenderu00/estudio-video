import { loadFont as loadOswald } from "@remotion/google-fonts/Oswald";
import { loadFont as loadMarker } from "@remotion/google-fonts/PermanentMarker";
import { loadFont as loadBarlow } from "@remotion/google-fonts/Barlow";
import type { Palette } from "./types";

export const OSWALD = loadOswald("normal", { weights: ["500", "600", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;
export const MARKER = loadMarker("normal", { weights: ["400"], subsets: ["latin"] }).fontFamily;
export const BARLOW = loadBarlow("normal", { weights: ["500", "600", "700"], subsets: ["latin", "latin-ext"] }).fontFamily;

// Palette (defaults = dark fantasy); replaced per project by setPalette() before the scenes render.
export const C: Record<string, string> = {
  red: "#E3263A",
  purple: "#A461FF",
  blue: "#5AA8F0",
  white: "#EDE6DA",
  bg: "#07070A",
  ink: "#15101A",
};
export const ACCENT: Record<string, string> = { red: C.red, purple: C.purple, blue: C.blue };
// text color on a brush box of each accent
export const ON_ACCENT: Record<string, string> = { red: "#F4EEE6", purple: "#1B0F2A", blue: "#0B1B2E" };
// fog tint per accent
export const FOG: Record<string, string> = { red: "#b8323f", purple: "#8f6ad8", blue: "#6f9fd0" };

export function setPalette(p?: Palette) {
  if (!p) return;
  C.white = p.white ?? C.white;
  C.bg = p.bg ?? C.bg;
  C.ink = p.ink ?? C.ink;
  for (const [k, v] of Object.entries(p.accents ?? {})) {
    ACCENT[k] = v.color;
    C[k] = v.color;
    ON_ACCENT[k] = v.text;
    FOG[k] = v.fog;
  }
}

/** "#rrggbb" -> "r,g,b" (for rgba() strings and <Flash color>) */
export function rgb(hex: string): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6), 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}
export const rgba = (hex: string, a: number) => `rgba(${rgb(hex)},${a})`;
// a scene names an accent from the palette; an overlay may also carry a raw #rrggbb
// (projeto.json -> brand.color), so both are accepted here
export const accent = (k: string) =>
  (k && k.startsWith("#") ? k : ACCENT[k]) ?? ACCENT.red ?? "#E3263A";

export const TEXT_SHADOW = "0 2px 14px rgba(0,0,0,0.85), 0 0 2px rgba(0,0,0,0.9)";
