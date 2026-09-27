import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame } from "remotion";
import { Backdrop, Flash } from "../components/fx";
import { Atmosphere, BeatFlashes, Layer, beatGlow, toBox } from "../components/Layers";
import { KineticText } from "../components/text";
import { artInfo } from "../lib/assets";
import { drift, highlighter, lineOf, prog } from "../lib/anim";
import { MARKER, OSWALD, TEXT_SHADOW, C, accent as accentOf, rgba } from "../theme";
import type { SceneProps } from "../types";

/** Emblem (alpha art, e.g. a sigil) with a slow sway and a glow pulse in the scene accent. */
export const Emblem: React.FC<{ art: string; left: number; top: number; width: number; frame: number; start?: number; color: string }> = ({
  art,
  left,
  top,
  width,
  frame,
  start = 8,
  color,
}) => {
  const a = artInfo(art);
  const h = width * (a.h / a.w);
  const inP = prog(frame, start, 40);
  const rot = Math.sin(frame / 90) * 3;
  const pulse = 0.35 + 0.3 * (0.5 + 0.5 * Math.sin(frame / 22));
  return (
    <div style={{ position: "absolute", left, top, width, height: h, opacity: inP, transform: `rotate(${rot.toFixed(3)}deg) scale(${(0.94 + 0.06 * inP).toFixed(4)})` }}>
      <Img
        src={staticFile(`art/${art}.${a.alpha ? "png" : "jpg"}`)}
        style={{ width, height: h, filter: `drop-shadow(0 0 ${(10 + 18 * pulse).toFixed(1)}px ${rgba(color, 0.35 + 0.5 * pulse)})` }}
      />
    </div>
  );
};

/** The lesson: an optional small setup line (`line1`) and the big statement (`line2`), emblem on the
 *  left, art on the right, a divider and a flash when the statement ends. */
export const Moral: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const l1 = lineOf(scene, "line1");
  const l2 = lineOf(scene, "line2") ?? scene.lines[scene.lines.length - 1];
  const divider = prog(frame, l2.rel + l2.durFrames - 6, 26);
  const bell = l2.rel + l2.durFrames + 3;
  const layer = scene.layers?.[0] ?? (scene.art ? { art: scene.art } : null);
  const em = scene.emblem;
  // statement in the accent color; with hl/hlFrom it turns white and only the marked words keep the accent
  const l2Hl = highlighter(l2, acc);

  return (
    <AbsoluteFill>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.3} />
      {layer ? (
        <Layer
          id={scene.id}
          spec={{ glow: scene.glow ?? { base: 0.18, amp: 0.1, period: 100 }, ...layer }}
          box={toBox(layer.box, { left: 1170, top: 0, width: 750, height: 1080 })}
          camera={scene.camera ?? [{ f: 0, s: 1.04, x: -0.15, y: 0 }, { f: D, s: 1.15, x: 0.05, y: -0.1 }]}
          mask="linear-gradient(to right, transparent 0%, #000 34%), linear-gradient(to bottom, #000 86%, transparent 100%)"
          depth={scene.depth ?? 10}
          glowExtra={beatGlow(scene, frame)}
        />
      ) : null}
      <Atmosphere scene={scene} particles={[["petals", 20], ["sparks", 18], ["dust", 16]]} fog={{ opacity: 0.12, speed: 0.4 }} />
      {em ? <Emblem art={em.art} left={em.left ?? 96} top={em.top ?? 255} width={em.width ?? 390} frame={frame} start={em.f ?? 8} color={acc} /> : null}

      <div style={{ position: "absolute", left: 500, width: 900, top: 226, textAlign: "center", transform: drift(frame, scene.id, 2) }}>
        {l1 ? (
          <KineticText
            text={l1.screenText}
            line={l1}
            style={{ fontFamily: OSWALD, fontWeight: 500, fontSize: 46, letterSpacing: 1.2, lineHeight: 1.3, color: rgba(C.white, 0.92), textShadow: TEXT_SHADOW }}
            hl={highlighter(l1, acc)}
          />
        ) : null}
        <KineticText
          text={l2.screenText}
          line={l2}
          mode="pop"
          style={{ marginTop: 44, fontFamily: MARKER, fontSize: 92, lineHeight: 1.12, color: l2Hl ? C.white : acc, textShadow: l2Hl ? TEXT_SHADOW : `0 0 34px ${rgba(acc, 0.45)}, ${TEXT_SHADOW}`, transform: "skewX(-5deg)" }}
          hl={l2Hl}
        />
      </div>
      <div style={{ position: "absolute", left: 560, width: 800, top: 842, height: 20, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div
          style={{
            width: 800,
            height: 2,
            background: `linear-gradient(90deg, ${rgba(acc, 0)}, ${rgba(acc, 0.95)} 30%, ${rgba(C.white, 0.95)} 50%, ${rgba(acc, 0.95)} 70%, ${rgba(acc, 0)})`,
            transform: `scaleX(${divider.toFixed(4)})`,
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 16,
            height: 16,
            border: `2px solid ${rgba(C.white, 0.95)}`,
            background: "#0b0810",
            transform: `rotate(45deg) scale(${divider.toFixed(4)})`,
            boxShadow: `0 0 14px ${rgba(acc, 0.9)}`,
          }}
        />
      </div>
      <Flash at={bell} color={acc} dur={40} peak={0.32} cy="45%" />
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};
