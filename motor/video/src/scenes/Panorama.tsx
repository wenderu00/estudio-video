import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Backdrop } from "../components/fx";
import { Atmosphere, BeatFlashes, Layer, beatGlow, beatImpacts, toBox } from "../components/Layers";
import { BrushQuote, BulletItem, ChapterTitle, KineticText, NumberBadge } from "../components/text";
import { drift, highlighter, knob, lineOf, linesOf, prog, shake } from "../lib/anim";
import { BARLOW, C, TEXT_SHADOW, accent as accentOf } from "../theme";
import type { SceneProps } from "../types";

/** Travelling shot over a wide image: title/intro/bullets on the left (fade out at the lead-in),
 *  a centered lead + painted quote, then a final line over the art. */
export const Panorama: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const title = lineOf(scene, "title");
  const intro = lineOf(scene, "intro");
  const bullets = linesOf(scene, "bullet");
  const lead = lineOf(scene, "quoteLead");
  const quote = lineOf(scene, "quote");
  const fin = lineOf(scene, "final");

  const badgeAt = title ? title.rel - 36 : 4;
  const leftAt = (lead ?? quote)?.rel;
  const leftOut = leftAt !== undefined ? prog(frame, leftAt - 14, 20) : 0;
  const centerOut = fin ? prog(frame, fin.rel - 14, 18) : 0;
  const layer = scene.layers?.[0] ?? { art: scene.art ?? "" };

  return (
    <AbsoluteFill style={{ transform: shake(frame, [badgeAt + 2, ...beatImpacts(scene)], 10, 9) }}>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.35} />
      <Layer
        id={scene.id}
        spec={{ glow: scene.glow ?? { base: 0.1, amp: 0.07, period: 80 }, flicker: scene.flicker, ...layer }}
        box={toBox(layer.box, { left: 0, top: 0, width: 1920, height: 1080 })}
        camera={scene.camera ?? [{ f: 0, s: 1.0, x: -1, y: 0 }, { f: D, s: 1.1, x: 1, y: 0 }]}
        imageMask="linear-gradient(to right, transparent 0%, #000 10%, #000 100%)"
        mask="linear-gradient(to bottom, #000 86%, transparent 100%)"
        depth={scene.depth ?? 18}
        glowExtra={beatGlow(scene, frame)}
      />
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, rgba(5,5,8,${(0.88 * (1 - leftOut)).toFixed(3)}) 0%, rgba(5,5,8,${(0.55 * (1 - leftOut)).toFixed(3)}) 34%, rgba(5,5,8,0) 52%)`,
        }}
      />
      <AbsoluteFill style={{ background: "linear-gradient(0deg, rgba(4,4,7,0.85) 0%, rgba(4,4,7,0) 34%)" }} />
      <Atmosphere scene={scene} particles={[["ash", 30], ["sparks", 28], ["dust", 18]]} fog={{ opacity: 0.15, speed: 0.5 }} />

      <div style={{ position: "absolute", inset: 0, opacity: 1 - leftOut, transform: drift(frame, scene.id, 2.5) }}>
        <NumberBadge num={scene.number ?? ""} accent={scene.accent} start={badgeAt} size={190} left={96} top={52} splat={knob(scene, "splat", 4)} />
        <ChapterTitle lines={scene.titleLines ?? []} accent={scene.accent} start={title ? title.rel - 30 : 10} fontSize={knob(scene, "titleSize", 88)} left={318} top={68} underline={470} />
        <div style={{ position: "absolute", left: 112, top: 350, width: 720, display: "flex", flexDirection: "column", gap: 34 }}>
          {intro ? (
            <KineticText
              text={intro.screenText}
              line={intro}
              style={{ fontFamily: BARLOW, fontWeight: 500, fontStyle: "italic", fontSize: 50, lineHeight: 1.2, color: C.white, textShadow: TEXT_SHADOW, marginBottom: 14 }}
            />
          ) : null}
          {bullets.map((b, i) => (
            <BulletItem
              key={b.id}
              icon={scene.icons?.[i] ?? "Circle"}
              text={b.screenText}
              start={b.rel - 5}
              dimAt={i + 1 < bullets.length ? bullets[i + 1].rel : leftAt}
              accent={scene.accent}
              fontSize={knob(scene, "fontSize", 54)}
              iconSize={knob(scene, "iconSize", 70)}
              maxWidth={620}
              italic={b.italic}
            />
          ))}
        </div>
      </div>

      <div style={{ position: "absolute", left: 0, width: 1920, top: 742, display: "flex", flexDirection: "column", alignItems: "center", opacity: 1 - centerOut }}>
        {lead ? (
          <KineticText
            text={lead.screenText}
            line={lead}
            style={{ fontFamily: BARLOW, fontWeight: 600, fontStyle: "italic", fontSize: 46, color: C.white, textShadow: TEXT_SHADOW, marginBottom: 34 }}
          />
        ) : null}
        {quote ? (
          <BrushQuote text={quote.screenText} line={quote} accent={scene.accent} start={quote.rel - 10} fontSize={knob(scene, "quoteSize", 84)} width={knob(scene, "quoteWidth", 760)} brush={knob(scene, "brush", 2)} rotate={-2} wordSync={false} />
        ) : null}
      </div>

      {fin ? (
        <div style={{ position: "absolute", left: 120, top: 800, width: 1180 }}>
          <KineticText
            text={fin.screenText}
            line={fin}
            style={{ fontFamily: BARLOW, fontWeight: 600, fontSize: 60, lineHeight: 1.2, color: C.white, textShadow: TEXT_SHADOW }}
            hl={highlighter(fin, acc)}
          />
        </div>
      ) : null}
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};
