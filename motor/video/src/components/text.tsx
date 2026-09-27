import React from "react";
import { interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, easeOut, pop, prog, syncTokens } from "../lib/anim";
import { BARLOW, C, MARKER, ON_ACCENT, OSWALD, TEXT_SHADOW, accent as accentOf, rgba } from "../theme";
import type { Accent, Line, TitleSeg } from "../types";
import { Icon } from "./icons";

// ------------------------------------------------------------------ number badge (splatter + digits)
export const NumberBadge: React.FC<{ num: string; accent: Accent; start: number; size: number; left: number; top: number; splat?: number }> = ({
  num,
  accent,
  start,
  size,
  left,
  top,
  splat = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (frame < start) return null;
  const p = pop(frame, start, fps, 10, 190);
  const q = pop(frame, start + 4, fps, 12, 210);
  const url = `url(${staticFile(`fx/splatter_${splat}.png`)})`;
  return (
    <div style={{ position: "absolute", left, top, width: size, height: size }}>
      <div
        style={{
          position: "absolute",
          inset: -size * 0.34,
          backgroundColor: accentOf(accent),
          WebkitMaskImage: url,
          maskImage: url,
          WebkitMaskSize: "100% 100%",
          maskSize: "100% 100%",
          transform: `scale(${(0.15 + 0.85 * p).toFixed(4)}) rotate(${((1 - p) * -55).toFixed(2)}deg)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: OSWALD,
          fontWeight: 700,
          fontSize: size * 0.58,
          letterSpacing: -2,
          color: C.ink,
          opacity: q,
          transform: `scale(${(2.1 - 1.1 * q).toFixed(4)})`,
        }}
      >
        {num}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ chapter title (words rise from a mask)
export const ChapterTitle: React.FC<{
  lines: TitleSeg[][];
  accent: Accent;
  start: number;
  fontSize: number;
  left: number;
  top: number;
  underline?: number;
  align?: "left" | "center";
}> = ({ lines, accent, start, fontSize, left, top, underline = 420, align = "left" }) => {
  const frame = useCurrentFrame();
  let idx = 0;
  const u = prog(frame, start + 10, 22);
  return (
    <div style={{ position: "absolute", left, top, textAlign: align }}>
      {lines.map((segs, li) => (
        <div key={li} style={{ overflow: "hidden", lineHeight: 1.04, paddingBottom: fontSize * 0.04, fontFamily: OSWALD, fontWeight: 700, fontSize, letterSpacing: 1, whiteSpace: "nowrap" }}>
          {segs.flatMap((seg, si) =>
            seg.t
              .split(/(\s+)/)
              .filter((w) => w.length > 0)
              .map((w, wi) => {
                if (/^\s+$/.test(w)) return <span key={`${si}-${wi}`} style={{ display: "inline-block", width: "0.26em" }} />;
                const p = prog(frame, start + idx++ * 3, 16);
                return (
                  <span
                    key={`${si}-${wi}`}
                    style={{
                      display: "inline-block",
                      color: seg.hl ? accentOf(accent) : C.white,
                      textShadow: seg.hl ? `0 0 26px ${accentOf(accent)}66, ${TEXT_SHADOW}` : TEXT_SHADOW,
                      transform: `translateY(${((1 - p) * 108).toFixed(2)}%)`,
                    }}
                  >
                    {w}
                  </span>
                );
              }),
          )}
        </div>
      ))}
      <div
        style={{
          marginTop: fontSize * 0.14,
          height: 4,
          width: underline,
          marginLeft: align === "center" ? "auto" : 0,
          marginRight: align === "center" ? "auto" : 0,
          background: `linear-gradient(90deg, ${accentOf(accent)}, ${accentOf(accent)}00)`,
          transform: `scaleX(${u.toFixed(4)})`,
          transformOrigin: align === "center" ? "50% 50%" : "0 50%",
          boxShadow: `0 0 12px ${accentOf(accent)}88`,
        }}
      />
    </div>
  );
};

// ------------------------------------------------------------------ bullet (icon pop + text wipe)
export const BulletItem: React.FC<{
  icon: string;
  text: string;
  start: number;
  dimAt?: number;
  accent: Accent;
  fontSize: number;
  iconSize: number;
  maxWidth: number;
  italic?: boolean;
}> = ({ icon, text, start, dimAt, accent, fontSize, iconSize, maxWidth, italic }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = pop(frame, start, fps, 11, 200);
  const q = prog(frame, start + 3, 18);
  const dim = dimAt !== undefined ? interpolate(frame, [dimAt, dimAt + 12], [1, 0.58], clamp) : 1;
  const visible = frame >= start - 1;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: iconSize * 0.42, opacity: visible ? dim : 0 }}>
      <div
        style={{
          width: iconSize,
          height: iconSize,
          flex: "none",
          transform: `scale(${p.toFixed(4)}) rotate(${((1 - p) * -30).toFixed(2)}deg)`,
          filter: `drop-shadow(0 0 10px ${accentOf(accent)}aa)`,
        }}
      >
        <Icon name={icon} size={iconSize} color={accentOf(accent)} />
      </div>
      <div
        style={{
          clipPath: `inset(-20% ${((1 - q) * 100).toFixed(2)}% -20% 0)`,
          transform: `translateX(${((1 - q) * -26).toFixed(2)}px)`,
          fontFamily: BARLOW,
          fontWeight: 600,
          fontStyle: italic ? "italic" : "normal",
          fontSize,
          lineHeight: 1.16,
          color: C.white,
          maxWidth,
          textShadow: TEXT_SHADOW,
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ kinetic text (word-synced reveal)
export const KineticText: React.FC<{
  text: string;
  line: Line;
  style: React.CSSProperties;
  hl?: (tok: string, i: number) => string | undefined;
  mode?: "rise" | "pop" | "fade";
  lead?: number;
}> = ({ text, line, style, hl, mode = "rise", lead = 2 }) => {
  const frame = useCurrentFrame();
  const toks = syncTokens(text, line);
  return (
    <div style={style}>
      {toks.map((t, i) => {
        const a = prog(frame, t.rel - lead, mode === "pop" ? 7 : 10, easeOut);
        const color = hl?.(t.tok, i);
        const tr =
          mode === "pop"
            ? `scale(${(0.72 + 0.28 * a).toFixed(4)})`
            : mode === "rise"
              ? `translateY(${((1 - a) * 16).toFixed(2)}px)`
              : "none";
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: a,
              transform: tr,
              filter: mode === "rise" && a < 0.99 ? `blur(${((1 - a) * 5).toFixed(2)}px)` : undefined,
              color: color ?? undefined,
              textShadow: color ? `0 0 22px ${color}66, ${TEXT_SHADOW}` : undefined,
              marginRight: "0.26em",
            }}
          >
            {t.tok}
          </span>
        );
      })}
    </div>
  );
};

// ------------------------------------------------------------------ brush-stroke quote
export const BrushQuote: React.FC<{
  text: string;
  line: Line;
  accent: Accent;
  start: number;
  fontSize: number;
  width: number;
  brush?: number;
  rotate?: number;
  align?: "left" | "center";
  textColor?: string;
  uppercase?: boolean;
  wordSync?: boolean;
}> = ({ text, line, accent, start, fontSize, width, brush = 0, rotate = -1.5, align = "center", textColor, uppercase, wordSync = true }) => {
  const frame = useCurrentFrame();
  if (frame < start - 1) return <div style={{ width, height: fontSize * 2.4 }} />;
  const p = prog(frame, start, 13);
  const url = `url(${staticFile(`fx/brush_${brush}.png`)})`;
  const toks = syncTokens(text, line);
  return (
    <div style={{ position: "relative", width, transform: `rotate(${rotate}deg)` }}>
      <div
        style={{
          position: "absolute",
          left: "-7%",
          right: "-7%",
          top: "-34%",
          bottom: "-34%",
          backgroundColor: accentOf(accent),
          WebkitMaskImage: url,
          maskImage: url,
          WebkitMaskSize: "100% 100%",
          maskSize: "100% 100%",
          clipPath: `inset(0 ${((1 - p) * 100).toFixed(2)}% 0 0)`,
          filter: `drop-shadow(0 6px 18px rgba(0,0,0,0.55))`,
        }}
      />
      <div
        style={{
          position: "relative",
          padding: `${fontSize * 0.18}px ${fontSize * 0.5}px`,
          fontFamily: MARKER,
          fontSize,
          lineHeight: 1.18,
          color: textColor ?? ON_ACCENT[accent],
          textAlign: align,
          textTransform: uppercase ? "uppercase" : undefined,
        }}
      >
        {toks.map((t, i) => {
          const a = wordSync ? prog(frame, t.rel - 2, 7) : prog(frame, start + 6 + i * 2, 8);
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                opacity: a,
                transform: `translateY(${((1 - a) * 12).toFixed(2)}px) scale(${(0.9 + 0.1 * a).toFixed(4)})`,
                marginRight: "0.24em",
              }}
            >
              {t.tok}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------ ornate label (framed caption)
export const OrnateLabel: React.FC<{ text: string; start: number; width: number; height: number; fontSize: number }> = ({
  text,
  start,
  width,
  height,
  fontSize,
}) => {
  const frame = useCurrentFrame();
  const p = prog(frame, start, 26);
  const q = prog(frame, start + 6, 20);
  if (frame < start) return <div style={{ width, height }} />;
  const W = width;
  const H = height;
  const n = 14;
  const frameD = `M ${n + 18} 3 H ${W - n - 18} L ${W - n - 3} ${n} V ${H - n} L ${W - n - 18} ${H - 3} H ${n + 18} L ${n + 3} ${H - n} V ${n} Z`;
  const L = 2 * (W - 2 * n - 36) + 2 * (H - 2 * n) + 4 * 21;
  const curlL = `M ${n + 3} ${H / 2} C ${n - 10} ${H / 2 - 16}, -2 ${H / 2 - 2}, 8 ${H / 2 + 8} M ${n + 3} ${H / 2} C ${n - 10} ${H / 2 + 16}, -2 ${H / 2 + 2}, 8 ${H / 2 - 8}`;
  const curlR = `M ${W - n - 3} ${H / 2} C ${W - n + 10} ${H / 2 - 16}, ${W + 2} ${H / 2 - 2}, ${W - 8} ${H / 2 + 8} M ${W - n - 3} ${H / 2} C ${W - n + 10} ${H / 2 + 16}, ${W + 2} ${H / 2 + 2}, ${W - 8} ${H / 2 - 8}`;
  return (
    <div style={{ position: "relative", width: W, height: H }}>
      <svg width={W} height={H} style={{ position: "absolute", inset: 0, overflow: "visible" }}>
        <path d={frameD} fill={`rgba(8,8,10,${(0.55 * q).toFixed(3)})`} stroke={rgba(C.white, 0.85)} strokeWidth={2.2} strokeDasharray={L} strokeDashoffset={L * (1 - p)} />
        <path d={curlL} fill="none" stroke={rgba(C.white, 0.85)} strokeWidth={2} opacity={q} />
        <path d={curlR} fill="none" stroke={rgba(C.white, 0.85)} strokeWidth={2} opacity={q} />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: OSWALD,
          fontWeight: 600,
          fontSize,
          letterSpacing: `${(3 + (1 - q) * 10).toFixed(2)}px`,
          color: rgba(C.white, 0.92),
          opacity: q,
          textShadow: TEXT_SHADOW,
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </div>
  );
};
