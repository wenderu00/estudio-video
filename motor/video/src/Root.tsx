import React from "react";
import { Composition, type CalculateMetadataFunction } from "remotion";
import { CamadasComp } from "./Camadas";
import type { CamadasProps, Timeline } from "./types";
import { VideoComp } from "./Video";

// The real timeline comes from the project (--props=.estudio/timeline-<fmt>.json).
const empty = (format: Timeline["format"], width: number, height: number): Timeline => ({
  format, title: "", fps: 30, width, height, durationInFrames: 30, duration: 1, audio: "", images: 0, art: {}, scenes: [],
});

const vazio: CamadasProps = { fps: 30, width: 1920, height: 1080, durationInFrames: 30, overlays: [] };

const meta: CalculateMetadataFunction<Timeline> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: props.fps,
  width: props.width,
  height: props.height,
});

const metaCamadas: CalculateMetadataFunction<CamadasProps> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: props.fps,
  width: props.width,
  height: props.height,
});

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Main" component={VideoComp} defaultProps={empty("main", 1920, 1080)} calculateMetadata={meta} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="Camadas" component={CamadasComp} defaultProps={vazio} calculateMetadata={metaCamadas} durationInFrames={30} fps={30} width={1920} height={1080} />
    <Composition id="Shorts" component={VideoComp} defaultProps={empty("shorts", 1080, 1920)} calculateMetadata={meta} durationInFrames={30} fps={30} width={1080} height={1920} />
  </>
);
