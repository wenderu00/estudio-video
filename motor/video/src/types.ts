export type Accent = string;

export type Word = { w: string; t: number; f: number; d: number; rel: number };

export type Line = {
  id: string;
  speaker: string;
  text: string;
  screen: string;
  screenText: string;
  t: number;
  dur: number;
  from: number;
  durFrames: number;
  rel: number;
  words: Word[];
  italic?: boolean;
  hl?: string[]; // on-screen words painted with the accent color
  hlFrom?: string; // paint from this word to the end
};

export type TitleSeg = { t: string; hl?: boolean };

/** Camera keyframe: f = scene-relative frame (resolved from `at`), zoom s (>=1 covers the box),
 *  focus x/y in -1..1 (-1 = left/top edge of the image aligned; beyond ±1 reveals background). */
export type KF = { f: number; s: number; x: number; y: number; at?: unknown };

export type Glow = { base: number; amp: number; period: number };

export type Timed = { f: number; dur?: number; at?: unknown };

export type LayerSpec = {
  art: string;
  box?: [number, number, number, number]; // left, top, width, height
  camera?: KF[];
  depth?: number;
  glow?: Glow;
  flicker?: number;
  mask?: string;
  imageMask?: string;
  saturate?: number;
  opacity?: number;
  enter?: Timed & { type?: "fade" | "emerge" | "brighten" };
  dim?: Timed & { amount?: number };
  flare?: Timed & { amount?: number };
};

export type FlashSpec = { color?: string; peak?: number; dur?: number; cx?: string; cy?: string };

export type Beat = {
  f: number;
  at?: unknown;
  shake?: boolean | number;
  flash?: boolean | FlashSpec;
  glow?: number; // extra glow on the scene's main art layer
  glowShape?: [number, number, number, number]; // frames before, to peak, to end (relative to f), residual level
};

export type PKind = "embers" | "sparks" | "ash" | "dust" | "petals";

export type Scene = {
  id: string;
  kind: "opening" | "chapter" | "panorama" | "moral" | "outro";
  name?: string;
  image: number;
  art?: string;
  accent: Accent;
  number?: string;
  titleLines?: TitleSeg[][];
  icons?: string[];
  music?: string;
  t0: number;
  t1: number;
  from: number;
  durFrames: number;
  transitionIn: { type: string; frames: number };
  transitionOut: null | { type: string; frames: number; holdFrames: number };
  lines: Line[];
  layers?: LayerSpec[];
  camera?: KF[];
  depth?: number;
  glow?: Glow;
  flicker?: number;
  particles?: { kind: PKind; count: number; color?: string }[];
  fog?: { opacity?: number; color?: string; speed?: number };
  beats?: Beat[];
  style?: Record<string, number | string | boolean>;
  emblem?: { art: string; left?: number; top?: number; width?: number; at?: unknown; f?: number };
  card?: { label?: string; title?: string; brush?: string };
  cta?: { button?: string };
  backdrop?: number;
};

export type ArtInfo = { w: number; h: number; img?: number; depth?: boolean; alpha?: boolean };

export type Palette = {
  bg: string;
  ink: string;
  white: string;
  accents: Record<string, { color: string; text: string; fog: string }>;
};

export type Timeline = {
  format: "main" | "shorts";
  title: string;
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  duration: number;
  audio: string;
  images: number;
  palette?: Palette;
  art: Record<string, ArtInfo>;
  scenes: Scene[];
};

export type SceneProps = { scene: Scene };

/** Video mode: an overlay drawn over the cut master (rendered alone, with alpha).
 *  A full-length element (watermark, progress bar) is NOT an overlay — it is ffmpeg, in
 *  montagem.py, or every frame of the video would have to go through the browser. */
export type OverlayKind =
  | "cartao"
  | "titulo"
  | "destaque"
  | "imagem"
  | "secao"
  | "tarja"
  | "callout"
  | "card"
  | "vinheta"
  | "telaFinal";

export type Overlay = {
  id: string;
  kind: OverlayKind;
  rel: number; // frame inside the overlay clip
  durFrames: number;
  title?: string;
  sub?: string;
  accent?: string; // a palette key, or a raw #rrggbb
  file?: string; // published under the project's public dir
  box?: [number, number, number, number]; // x, y, w, h as 0..1 of the frame
  position?: "left" | "right" | "center";
  n?: string; // secao: the chapter number
  name?: string; // tarja: who is speaking
  role?: string; // tarja: what they do
  icon?: string; // callout: any Lucide name
  items?: string[]; // card: one line each, revealed in turn
  cta?: string; // telaFinal: the closing prompt
  depth?: boolean; // imagem: draw with 2.5D parallax (a depth map was generated for it)
};

export type Brand = { logo?: string; name?: string; handle?: string; color?: string };

export type CamadasProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  palette?: Palette;
  brand?: Brand;
  /** fraction of the frame height the burned captions take at the bottom */
  capBase?: number;
  overlays: Overlay[];
};
