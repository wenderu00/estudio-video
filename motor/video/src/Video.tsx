import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Grain, Vignette } from "./components/fx";
import { OVERLAP, SceneShell } from "./components/SceneShell";
import { useAssets } from "./lib/assets";
import { Chapter } from "./scenes/Chapter";
import { Moral } from "./scenes/Moral";
import { Opening } from "./scenes/Opening";
import { Outro } from "./scenes/Outro";
import { Panorama } from "./scenes/Panorama";
import { ShortsChapter, ShortsMoral, ShortsOpening } from "./scenes/Shorts";
import { setPalette } from "./theme";
import type { Scene, SceneProps, Timeline } from "./types";

const pick = (s: Scene, fmt: Timeline["format"]): React.FC<SceneProps> => {
  if (fmt === "shorts") {
    if (s.kind === "opening") return ShortsOpening;
    if (s.kind === "moral" || s.kind === "outro") return ShortsMoral;
    return ShortsChapter;
  }
  switch (s.kind) {
    case "opening":
      return Opening;
    case "chapter":
      return Chapter;
    case "panorama":
      return Panorama;
    case "moral":
      return Moral;
    default:
      return Outro;
  }
};

export const VideoComp: React.FC<Timeline> = (tl) => {
  setPalette(tl.palette);
  const ready = useAssets(tl);
  if (!ready) return <AbsoluteFill style={{ backgroundColor: "#000" }} />;
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {tl.scenes.map((sc, i) => {
        const next = tl.scenes[i + 1];
        const exit = next && OVERLAP.has(next.transitionIn.type) ? next.transitionIn : null;
        const Comp = pick(sc, tl.format);
        return (
          <Sequence key={sc.id} from={sc.from} durationInFrames={sc.durFrames} name={sc.id} premountFor={30}>
            <SceneShell scene={sc} exit={exit}>
              <Comp scene={sc} />
            </SceneShell>
          </Sequence>
        );
      })}
      <Grain opacity={tl.format === "main" ? 0.085 : 0.07} />
      <Vignette strength={tl.format === "main" ? 0.72 : 0.55} />
      {tl.audio ? <Audio src={staticFile(tl.audio)} /> : null}
    </AbsoluteFill>
  );
};
