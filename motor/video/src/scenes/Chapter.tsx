import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Backdrop, Flash } from "../components/fx";
import { Atmosphere, BeatFlashes, Layer, beatGlow, beatImpacts, toBox } from "../components/Layers";
import { BrushQuote, BulletItem, ChapterTitle, KineticText, NumberBadge } from "../components/text";
import { drift, knob, lineOf, linesOf, shake } from "../lib/anim";
import { BARLOW, C, TEXT_SHADOW, accent as accentOf } from "../theme";
import type { SceneProps } from "../types";

/** Numbered chapter: badge + title, bullets that appear with the narration, optional statement and
 *  a painted quote, over the chapter's art on the right. */
export const Chapter: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const title = lineOf(scene, "title");
  const bullets = linesOf(scene, "bullet");
  const statement = lineOf(scene, "statement");
  const quote = lineOf(scene, "quote");

  const badgeAt = title ? title.rel - 36 : 4;
  const titleAt = title ? title.rel - 30 : 10;
  const longest = Math.max(1, ...(scene.titleLines ?? []).map((l) => l.map((s) => s.t).join("").length));
  const fs = Math.min(92, 600 / (longest * 0.47));
  const nTitle = scene.titleLines?.length ?? 1;
  const colTop = 74 + nTitle * fs * 1.08 + 88;
  const nextAfter = (i: number) => (i + 1 < bullets.length ? bullets[i + 1].rel : (statement ?? quote)?.rel);

  const impacts = [badgeAt + 2, ...beatImpacts(scene)];
  if (knob(scene, "shakeBullets", false)) bullets.forEach((b) => impacts.push(b.rel - 1));
  const layer = scene.layers?.[0] ?? { art: scene.art ?? "" };

  return (
    <AbsoluteFill style={{ transform: shake(frame, impacts, knob(scene, "shakeAmp", 12), 8) }}>
      <Backdrop image={scene.image} opacity={scene.backdrop ?? 0.5} />
      <Layer
        id={scene.id}
        spec={{ glow: scene.glow, flicker: scene.flicker, ...layer }}
        box={toBox(layer.box, { left: 790, top: 0, width: 1130, height: 1080 })}
        camera={scene.camera ?? [{ f: 0, s: 1.04, x: 0.1, y: 0.3 }, { f: D, s: 1.2, x: 0.45, y: -0.5 }]}
        mask="linear-gradient(to right, transparent 0%, #000 26%), linear-gradient(to bottom, #000 84%, transparent 100%)"
        depth={scene.depth ?? 14}
        glowExtra={beatGlow(scene, frame)}
      />
      <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(5,5,8,0.92) 0%, rgba(5,5,8,0.7) 38%, rgba(5,5,8,0) 60%)" }} />
      <Atmosphere scene={scene} particles={[["embers", 30], ["dust", 14]]} fog={{ opacity: 0.14, speed: 0.55 }} />

      <div style={{ position: "absolute", inset: 0, transform: drift(frame, scene.id, 2.5) }}>
        <NumberBadge num={scene.number ?? ""} accent={scene.accent} start={badgeAt} size={190} left={96} top={52} splat={knob(scene, "splat", 0)} />
        <ChapterTitle lines={scene.titleLines ?? []} accent={scene.accent} start={titleAt} fontSize={fs} left={318} top={68} underline={470} />
        <div style={{ position: "absolute", left: 112, top: colTop, width: 690, display: "flex", flexDirection: "column", gap: knob(scene, "bulletGap", 38) }}>
          {bullets.map((b, i) => (
            <BulletItem
              key={b.id}
              icon={scene.icons?.[i] ?? "Circle"}
              text={b.screenText}
              start={b.rel - 5}
              dimAt={nextAfter(i)}
              accent={scene.accent}
              fontSize={knob(scene, "fontSize", 56)}
              iconSize={knob(scene, "iconSize", 74)}
              maxWidth={600}
              italic={b.italic}
            />
          ))}
          {statement ? (
            <KineticText
              text={statement.screenText}
              line={statement}
              style={{ marginTop: 22, fontFamily: BARLOW, fontWeight: 500, fontSize: 50, lineHeight: 1.2, color: C.white, maxWidth: 640, textShadow: TEXT_SHADOW }}
            />
          ) : null}
          {quote ? (
            <div style={{ marginTop: 34, marginLeft: 10 }}>
              <BrushQuote
                text={quote.screenText}
                line={quote}
                accent={scene.accent}
                start={quote.rel - 14}
                fontSize={knob(scene, "quoteSize", 54)}
                width={knob(scene, "quoteWidth", 700)}
                brush={knob(scene, "brush", 0)}
              />
            </div>
          ) : null}
        </div>
      </div>
      <Flash at={badgeAt + 1} color={acc} dur={16} peak={0.22} cx="12%" cy="12%" />
      <BeatFlashes scene={scene} />
    </AbsoluteFill>
  );
};
