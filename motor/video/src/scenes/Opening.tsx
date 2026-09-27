import React from "react";
import { AbsoluteFill, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, Flash } from "../components/fx";
import { Atmosphere, BeatFlashes, Layer, beatImpacts, toBox } from "../components/Layers";
import { KineticText, OrnateLabel } from "../components/text";
import { clamp, easeInOut, highlighter, lineOf, linesOf, pop, prog, shake } from "../lib/anim";
import { C, MARKER, OSWALD, TEXT_SHADOW, accent as accentOf, rgba } from "../theme";
import type { KF, LayerSpec, SceneProps } from "../types";

const MASK_LEFT = "linear-gradient(to right, #000 87%, transparent 100%), linear-gradient(to bottom, #000 80%, transparent 100%)";
const MASK_RIGHT = "linear-gradient(to left, #000 55%, transparent 96%), linear-gradient(to bottom, #000 82%, transparent 100%)";
const MASK_FULL = "linear-gradient(to bottom, #000 80%, transparent 100%)";

/** Hook lines (hook1, hook2…) centered, then a title card: `label` (framed), `title` (slam), `brush` (painted). */
export const Opening: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const hooks = linesOf(scene, "hook");
  const label = lineOf(scene, "label");
  const title = lineOf(scene, "title");
  const brush = lineOf(scene, "brush") ?? lineOf(scene, "porela");
  const layers: LayerSpec[] = scene.layers ?? (scene.art ? [{ art: scene.art, enter: { f: 0, type: "emerge" } }] : []);
  const two = layers.length > 1;
  const boxes = two
    ? [{ left: 0, top: 0, width: 1000, height: 1080 }, { left: 900, top: 0, width: 1020, height: 1080 }]
    : [{ left: 0, top: 0, width: 1920, height: 1080 }];
  const cams: KF[][] = [
    [{ f: 0, s: 1.02, x: two ? 1 : 0, y: 0.1 }, { f: D, s: 1.15, x: two ? 1 : 0.2, y: -0.25 }],
    [{ f: 0, s: 1.12, x: 0.25, y: 0.35 }, { f: D, s: 1.02, x: 0.35, y: 0 }],
  ];

  const settle = label ? prog(frame, label.rel - 34, 30, easeInOut) : 0;
  const slam = title ? pop(frame, title.rel - 3, fps, 12, 220) : 0;
  const porP = brush ? prog(frame, brush.rel - 4, 11) : 0;
  const underline = brush ? prog(frame, brush.rel + 5, 14) : 0;
  const bellGlow = brush ? interpolate(frame, [brush.rel, brush.rel + 6, brush.rel + 60], [0, 1, 0.25], clamp) : 0;
  const impacts = [...(title ? [title.rel - 2] : []), ...(brush ? [brush.rel] : []), ...beatImpacts(scene)];
  const labelText = label?.screenText ?? scene.card?.label;
  const labelW = labelText ? Math.max(420, Math.round(labelText.length * 42 * 0.62 + 150)) : 0;
  const titleSize = title ? Math.min(156, 1780 / Math.max(1, title.screenText.length * 0.52)) : 156;
  const brushSize = brush ? Math.min(212, 1700 / Math.max(1, brush.screenText.length * 0.62)) : 212;

  return (
    <AbsoluteFill style={{ transform: shake(frame, impacts, 11, 8) }}>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.35} />
      {layers.map((l, i) => (
        <Layer
          key={i}
          id={`${scene.id}-l${i}`}
          spec={l}
          box={toBox(l.box, boxes[Math.min(i, boxes.length - 1)])}
          camera={cams[Math.min(i, 1)]}
          mask={two ? (i === 0 ? MASK_LEFT : MASK_RIGHT) : MASK_FULL}
          depth={i === 0 ? 14 : 10}
        />
      ))}
      <Atmosphere scene={scene} particles={[["embers", 34], ["ash", 16], ["dust", 24]]} fog={{ opacity: 0.15, color: "#a2a2b4", speed: 0.5 }} />

      {/* hook: centered first, then settles below the title as its subtitle */}
      {hooks.length ? (
        <div
          style={{
            position: "absolute",
            left: 330,
            width: 1260,
            top: interpolate(settle, [0, 1], [700, 816]),
            transform: `scale(${interpolate(settle, [0, 1], [1, 0.8]).toFixed(4)})`,
            transformOrigin: "50% 0",
            textAlign: "center",
            fontFamily: OSWALD,
            fontWeight: 500,
            fontSize: 52,
            lineHeight: 1.28,
            letterSpacing: 1.5,
            color: C.white,
            textShadow: TEXT_SHADOW,
          }}
        >
          {hooks.map((h) => (
            <KineticText key={h.id} text={h.screenText} line={h} style={{ display: "inline" }} hl={highlighter(h, acc)} />
          ))}
        </div>
      ) : null}

      {labelText ? (
        <div style={{ position: "absolute", left: (1920 - labelW) / 2, top: 138 }}>
          <OrnateLabel text={labelText} start={label ? label.rel - 8 : 6} width={labelW} height={80} fontSize={42} />
        </div>
      ) : null}
      {title && frame >= title.rel - 3 ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            width: 1920,
            top: 238,
            textAlign: "center",
            fontFamily: OSWALD,
            fontWeight: 700,
            fontSize: titleSize,
            letterSpacing: 3,
            color: C.white,
            textShadow: "0 6px 26px rgba(0,0,0,0.9)",
            opacity: Math.min(1, slam * 1.6),
            transform: `scale(${(1.45 - 0.45 * slam).toFixed(4)})`,
          }}
        >
          {title.screenText}
        </div>
      ) : null}
      {brush ? (
        <>
          <div
            style={{
              position: "absolute",
              left: 0,
              width: 1920,
              top: 418,
              textAlign: "center",
              fontFamily: MARKER,
              fontSize: brushSize,
              color: acc,
              transform: "skewX(-7deg)",
              clipPath: `inset(-20% ${((1 - porP) * 100).toFixed(2)}% -20% 0)`,
              textShadow: `0 0 ${(20 + 50 * bellGlow).toFixed(1)}px ${rgba(acc, 0.35 + 0.45 * bellGlow)}, 0 6px 20px rgba(0,0,0,0.9)`,
            }}
          >
            {brush.screenText}
          </div>
          <div
            style={{
              position: "absolute",
              left: 560,
              top: 668,
              width: 800,
              height: 46,
              backgroundColor: acc,
              WebkitMaskImage: `url(${staticFile("fx/brush_1.png")})`,
              maskImage: `url(${staticFile("fx/brush_1.png")})`,
              WebkitMaskSize: "100% 100%",
              maskSize: "100% 100%",
              clipPath: `inset(0 ${((1 - underline) * 100).toFixed(2)}% 0 0)`,
              opacity: 0.9,
            }}
          />
          <Flash at={brush.rel} color={acc} dur={30} peak={0.35} cy="48%" />
        </>
      ) : null}
      {title ? <Flash at={title.rel - 2} color="255,240,230" dur={14} peak={0.28} /> : null}
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};
