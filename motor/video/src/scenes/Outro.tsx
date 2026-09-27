import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Bell, MessageCircleMore } from "lucide-react";
import { Atmosphere, Layer, toBox } from "../components/Layers";
import { clamp, easeInOut, highlighter, knob, lineOf, norm, pop, prog, syncTokens } from "../lib/anim";
import { BARLOW, C, MARKER, OSWALD, TEXT_SHADOW, accent as accentOf, rgba } from "../theme";
import type { SceneProps } from "../types";

/** Question to the audience + "comment • subscribe" call to action; then the text lifts away to leave
 *  room for YouTube's end-screen elements. `cta` screenText: "text • BUTTON". */
export const Outro: React.FC<SceneProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const D = scene.durFrames;
  const acc = accentOf(scene.accent);
  const q = lineOf(scene, "question") ?? scene.lines[0];
  const cta = lineOf(scene, "cta");
  const qt = syncTokens(q.screenText, q);
  const pIdx = qt.findIndex((t) => /[?.!]$/.test(t.tok));
  const split = pIdx >= 0 && pIdx + 1 <= Math.ceil(qt.length / 2) ? pIdx + 1 : Math.min(2, qt.length);
  const qhl = highlighter(q, acc);
  const [ctaText, ctaBtn] = (cta?.screenText ?? "").split("•").map((s) => s.trim());
  const ct = cta ? syncTokens(cta.screenText, cta) : [];
  const nText = ctaText ? ctaText.split(/\s+/).filter(Boolean).length : 0;
  const button = scene.cta?.button ?? (ctaBtn ? ctaBtn.toUpperCase() : "INSCREVA-SE");
  const endAt = (cta ?? q).rel + (cta ?? q).durFrames + 36;
  const lift = prog(frame, endAt, 34, easeInOut);
  const ctaOut = prog(frame, endAt, 22);
  const fadeEnd = interpolate(frame, [D - 50, D - 4], [0, 1], clamp);
  const btnTok = ct.slice(nText).find((t) => norm(t.tok) !== "");
  const subAt = btnTok?.rel ?? (cta ? cta.rel + 40 : 0);
  const subP = cta ? pop(frame, subAt - 2, fps, 10, 200) : 0;
  const pulse = frame > subAt + 20 ? 1 + 0.04 * Math.sin((frame - subAt) / 7) : 1;
  const btnColor = String(knob(scene, "buttonColor", "#E3263A"));

  const word = (t: { tok: string; rel: number }, i: number, style: React.CSSProperties) => {
    const a = prog(frame, t.rel - 2, 8);
    return (
      <span key={i} style={{ display: "inline-block", opacity: a, transform: `translateY(${((1 - a) * 18).toFixed(2)}px)`, marginRight: "0.25em", ...style }}>
        {t.tok}
      </span>
    );
  };
  const layer = scene.layers?.[0] ?? (scene.art ? { art: scene.art } : null);

  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ backgroundColor: "#050507" }} />
      {layer ? (
        <Layer
          id={`${scene.id}-bg`}
          spec={{ glow: scene.glow ?? { base: 0.2, amp: 0.08, period: 110 }, opacity: knob(scene, "artOpacity", 0.62), ...layer }}
          box={toBox(layer.box, { left: 0, top: 0, width: 1920, height: 1080 })}
          camera={scene.camera ?? [{ f: 0, s: 1.0, x: 0.3, y: 0.3 }, { f: D, s: 1.1, x: 0.45, y: -0.2 }]}
          depth={scene.depth ?? 8}
        />
      ) : null}
      <AbsoluteFill style={{ background: "linear-gradient(90deg, rgba(4,4,7,0.94) 0%, rgba(4,4,7,0.72) 42%, rgba(4,4,7,0.15) 75%)" }} />
      <Atmosphere scene={scene} particles={[["petals", 14], ["dust", 22]]} fog={{ opacity: 0.12, speed: 0.35 }} />

      <div style={{ position: "absolute", left: 150, top: 300, width: 1100, transform: `translateY(${(-lift * 190).toFixed(1)}px) scale(${(1 - lift * 0.22).toFixed(4)})`, transformOrigin: "0 0" }}>
        <div style={{ fontFamily: OSWALD, fontWeight: 700, fontSize: 132, lineHeight: 1.0, color: C.white, textShadow: TEXT_SHADOW, letterSpacing: 2 }}>
          {qt.slice(0, split).map((t, i) => word(t, i, {}))}
        </div>
        <div style={{ marginTop: 18, fontFamily: MARKER, fontSize: 78, lineHeight: 1.15, color: C.white, textShadow: TEXT_SHADOW }}>
          {qt.slice(split).map((t, i) => {
            const c = qhl?.(t.tok, i + split);
            return word(t, i, c ? { color: c, textShadow: `0 0 26px ${rgba(c, 0.5)}, ${TEXT_SHADOW}` } : {});
          })}
        </div>
        {cta ? (
          <div style={{ marginTop: 56, display: "flex", alignItems: "center", gap: 28, opacity: 1 - ctaOut }}>
            <div style={{ transform: `scale(${pop(frame, cta.rel - 3, fps).toFixed(4)})` }}>
              <MessageCircleMore size={54} color={acc} strokeWidth={2.1} fill={rgba(acc, 0.2)} />
            </div>
            <div style={{ fontFamily: BARLOW, fontWeight: 600, fontSize: 44, color: C.white, textShadow: TEXT_SHADOW }}>
              {ct.slice(0, nText).map((t, i) => word(t, i, {}))}
            </div>
            <div
              style={{
                marginLeft: 16,
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 26px",
                borderRadius: 40,
                background: btnColor,
                boxShadow: `0 8px 28px ${rgba(btnColor, 0.45)}`,
                fontFamily: OSWALD,
                fontWeight: 600,
                fontSize: 34,
                letterSpacing: 1.5,
                color: "#fff",
                transform: `scale(${(subP * pulse).toFixed(4)})`,
                opacity: subP,
              }}
            >
              <Bell size={30} color="#fff" strokeWidth={2.4} style={{ transform: `rotate(${(Math.sin(frame / 3) * 14 * Math.exp(-Math.max(0, frame - subAt) / 25)).toFixed(2)}deg)` }} />
              {button}
            </div>
          </div>
        ) : null}
      </div>
      <AbsoluteFill style={{ backgroundColor: "#000", opacity: fadeEnd }} />
    </AbsoluteFill>
  );
};
