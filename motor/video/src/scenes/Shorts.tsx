import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop } from "../components/fx";
import { Atmosphere, BeatFlashes, Layer, beatGlow, beatImpacts, toBox } from "../components/Layers";
import { BrushQuote, ChapterTitle, KineticText, NumberBadge, OrnateLabel } from "../components/text";
import { clamp, highlighter, knob, lineOf, linesOf, pop, prog, shake } from "../lib/anim";
import { C, MARKER, OSWALD, TEXT_SHADOW, accent as accentOf, rgba } from "../theme";
import type { KF, LayerSpec, SceneProps } from "../types";
import { Emblem } from "./Moral";
import { Flash } from "../components/fx";

// 1080×1920: art on top (~60%), badge/title in the middle, captions below; the bottom ~420 px and
// the top ~200 px stay clear of the YouTube Shorts UI.
const ART_BOX = { left: 0, top: 0, width: 1080, height: 1190 };
const ART_MASK = "linear-gradient(to bottom, #000 70%, transparent 100%)";
const CAP_STYLE: React.CSSProperties = {
  fontFamily: OSWALD,
  fontWeight: 600,
  fontSize: 66,
  lineHeight: 1.14,
  letterSpacing: 1,
  textTransform: "uppercase",
  color: C.white,
  textAlign: "center",
  textShadow: TEXT_SHADOW,
};

// ------------------------------------------------------------------ opening
/** Hook lines swap at the top; a static title card (`card`: label/title/brush) sits in the middle. */
export const ShortsOpening: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const hooks = linesOf(scene, "hook");
  const card = scene.card ?? {};
  const slam = pop(frame, 4, fps, 12, 220);
  const porP = prog(frame, 12, 10);
  const layers: LayerSpec[] = scene.layers ?? (scene.art ? [{ art: scene.art, enter: { f: 0, type: "brighten" } }] : []);
  const cams: KF[][] = [
    [{ f: 0, s: 1.05, x: 0.35, y: 0 }, { f: D, s: 1.2, x: 0.6, y: -0.3 }],
    [{ f: 0, s: 1.1, x: 0.3, y: 0.3 }, { f: D, s: 1.02, x: 0.4, y: 0 }],
  ];
  const labelW = card.label ? Math.max(360, Math.round(card.label.length * 36 * 0.62 + 130)) : 0;
  const titleSize = card.title ? Math.min(110, 980 / Math.max(1, card.title.length * 0.5)) : 110;
  const brushSize = card.brush ? Math.min(168, 980 / Math.max(1, card.brush.length * 0.62)) : 168;
  return (
    <AbsoluteFill style={{ transform: shake(frame, card.title ? [4, ...beatImpacts(scene)] : beatImpacts(scene), 10, 8) }}>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.3} />
      {layers.map((l, i) => (
        <Layer
          key={i}
          id={`${scene.id}-sl${i}`}
          spec={l}
          box={toBox(l.box, i === 0 ? ART_BOX : { left: 330, top: 60, width: 750, height: 1060 })}
          camera={cams[Math.min(i, 1)]}
          mask={i === 0 ? ART_MASK : "linear-gradient(to left, #000 55%, transparent 98%), linear-gradient(to bottom, #000 70%, transparent 100%)"}
          depth={12}
        />
      ))}
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(4,4,7,0.9) 0%, rgba(4,4,7,0.55) 22%, rgba(4,4,7,0.2) 30%, rgba(4,4,7,0) 38%)" }} />
      <Atmosphere scene={scene} particles={[["embers", 30], ["dust", 18]]} fog={{ opacity: 0.14, color: "#a2a2b4" }} />
      <div style={{ position: "absolute", left: 60, width: 960, top: 250, ...CAP_STYLE, fontSize: 78, lineHeight: 1.1 }}>
        {hooks.map((h, i) => {
          const out = i + 1 < hooks.length ? 1 - prog(frame, hooks[i + 1].rel - 6, 8) : 1;
          return (
            <div key={h.id} style={{ position: "absolute", left: 0, right: 0, top: 0, opacity: out }}>
              <KineticText text={h.screenText} line={h} style={{}} mode="pop" hl={highlighter(h, acc)} />
            </div>
          );
        })}
      </div>
      {card.label ? (
        <div style={{ position: "absolute", left: (1080 - labelW) / 2, top: 1040 }}>
          <OrnateLabel text={card.label} start={0} width={labelW} height={72} fontSize={36} />
        </div>
      ) : null}
      {card.title ? (
        <div style={{ position: "absolute", left: 0, width: 1080, top: 1128, textAlign: "center", fontFamily: OSWALD, fontWeight: 700, fontSize: titleSize, color: C.white, textShadow: TEXT_SHADOW, opacity: Math.min(1, slam * 1.6), transform: `scale(${(1.4 - 0.4 * slam).toFixed(4)})` }}>
          {card.title}
        </div>
      ) : null}
      {card.brush ? (
        <div style={{ position: "absolute", left: 0, width: 1080, top: 1250, textAlign: "center", fontFamily: MARKER, fontSize: brushSize, color: acc, transform: "skewX(-7deg)", clipPath: `inset(-20% ${((1 - porP) * 100).toFixed(2)}% -20% 0)`, textShadow: `0 0 30px ${rgba(acc, 0.45)}, 0 6px 20px rgba(0,0,0,0.9)` }}>
          {card.brush}
        </div>
      ) : null}
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ chapters (incl. panorama)
export const ShortsChapter: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const D = scene.durFrames;
  const title = lineOf(scene, "title");
  const badgeAt = title ? title.rel - 12 : 6;
  const longest = Math.max(1, ...(scene.titleLines ?? []).map((l) => l.map((s) => s.t).join("").length));
  const fs = Math.min(84, 700 / (longest * 0.47));
  const spoken = scene.lines.filter((l) => l.screen !== "title");
  const impacts = [badgeAt + 2, ...beatImpacts(scene)];
  const sc = knob<number | boolean>(scene, "shakeCaptions", false);
  if (sc) spoken.filter((l) => l.screen === "caption").slice(0, sc === true ? undefined : Number(sc)).forEach((l) => impacts.push(l.rel - 1));
  const layer = scene.layers?.[0] ?? { art: scene.art ?? "" };

  return (
    <AbsoluteFill style={{ transform: shake(frame, impacts, 11, 8) }}>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.45} />
      <Layer
        id={`sh-${scene.id}`}
        spec={{ glow: scene.glow, flicker: scene.flicker, ...layer }}
        box={toBox(layer.box, ART_BOX)}
        camera={scene.camera ?? [{ f: 0, s: 1.05, x: 0.2, y: 0.1 }, { f: D, s: 1.22, x: 0.5, y: -0.5 }]}
        mask={ART_MASK}
        depth={scene.depth ?? 12}
        glowExtra={beatGlow(scene, frame)}
      />
      <Atmosphere scene={scene} particles={[["embers", 24], ["ash", 18]]} fog={{ opacity: 0.14 }} />
      <NumberBadge num={scene.number ?? ""} accent={scene.accent} start={badgeAt} size={150} left={50} top={1010} splat={(parseInt(scene.number ?? "1", 10) || 1) % 5} />
      <ChapterTitle lines={scene.titleLines ?? []} accent={scene.accent} start={badgeAt + 4} fontSize={fs} left={226} top={1016} underline={420} />
      {spoken.map((ln, i) => {
        const isLead = ln.screen === "quoteLead";
        // a lead-in ("Ele só quer:") stays on screen above the quote that follows it
        const until = spoken[i + (isLead ? 2 : 1)];
        const a = ln.rel - 4;
        const b = until ? until.rel - 3 : D + 10;
        if (frame < a - 2 || frame > b + 6) return null;
        const out = interpolate(frame, [b - 4, b + 2], [1, 0], clamp);
        const isQuote = ln.screen === "quote";
        const afterLead = isQuote && spoken[i - 1]?.screen === "quoteLead";
        const long = ln.screenText.length > 20;
        return (
          <div key={ln.id} style={{ position: "absolute", left: 60, width: 880, top: isLead ? 1250 : afterLead ? 1346 : 1290, display: "flex", justifyContent: "center", opacity: out }}>
            {isQuote ? (
              <BrushQuote text={ln.screenText} line={ln} accent={scene.accent} start={a - 4} fontSize={long ? 54 : 74} width={long ? 820 : 640} brush={i % 3} uppercase={knob(scene, "quoteUppercase", false)} wordSync={ln.screenText.length > 16} />
            ) : (
              <KineticText
                text={ln.screenText}
                line={ln}
                mode="pop"
                style={{ ...CAP_STYLE, fontSize: isLead ? 50 : ln.screenText.length > 40 ? 56 : 66, fontStyle: isLead || ln.italic ? "italic" : undefined }}
                hl={highlighter(ln, accentOf(scene.accent))}
              />
            )}
          </div>
        );
      })}
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ moral / closing statement
export const ShortsMoral: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const l1 = lineOf(scene, "line1");
  const l = lineOf(scene, "line2") ?? scene.lines[scene.lines.length - 1];
  const bell = l.rel + l.durFrames + 2;
  const layer = scene.layers?.[0] ?? (scene.art ? { art: scene.art } : null);
  const em = scene.emblem;
  return (
    <AbsoluteFill>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.3} />
      {layer ? (
        <Layer
          id={`sh-${scene.id}`}
          spec={{ glow: scene.glow ?? { base: 0.2, amp: 0.1, period: 70 }, ...layer }}
          box={toBox(layer.box, { left: 0, top: 0, width: 1080, height: 1080 })}
          camera={scene.camera ?? [{ f: 0, s: 1.04, x: 0.2, y: 0 }, { f: D, s: 1.16, x: 0.35, y: -0.1 }]}
          mask={ART_MASK}
          depth={scene.depth ?? 10}
        />
      ) : null}
      <Atmosphere scene={scene} particles={[["petals", 16], ["sparks", 14]]} fog={{ opacity: 0.12 }} />
      {em ? <Emblem art={em.art} left={em.left ?? 40} top={em.top ?? 120} width={em.width ?? 210} frame={frame} start={em.f ?? 4} color={acc} /> : null}
      <div style={{ position: "absolute", left: 70, width: 940, top: l1 ? 960 : 1030, textAlign: "center" }}>
        {l1 ? (
          <KineticText text={l1.screenText} line={l1} style={{ fontFamily: OSWALD, fontWeight: 500, fontSize: 44, lineHeight: 1.2, color: rgba(C.white, 0.92), textShadow: TEXT_SHADOW, marginBottom: 26 }} />
        ) : null}
        <KineticText text={l.screenText} line={l} mode="pop" style={{ fontFamily: MARKER, fontSize: 74, lineHeight: 1.14, color: C.white, textShadow: TEXT_SHADOW }} hl={highlighter(l, acc)} />
      </div>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, height: 1920, pointerEvents: "none" }}>
        <Flash at={bell} color={acc} dur={34} peak={0.35} cy="40%" />
      </div>
      <BeatFlashes scene={scene} />
      <AbsoluteFill style={{ backgroundColor: "#000", opacity: interpolate(frame, [D - 18, D - 2], [0, 1], clamp) }} />
    </AbsoluteFill>
  );
};
