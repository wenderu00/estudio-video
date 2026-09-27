import { useEffect, useState } from "react";
import { continueRender, delayRender, staticFile } from "remotion";
import type { ArtInfo, Timeline } from "../types";

// Registries filled once per page from the timeline (props) before any scene mounts.
export const ART: Record<string, ArtInfo> = {};
export const DEPTH: Record<string, string> = {}; // depth maps as data URIs (feImage must never load late)

export function artInfo(name: string): ArtInfo {
  const a = ART[name];
  if (!a) throw new Error(`arte "${name}" não existe em art.json — rode \`estudio.py arte\``);
  return a;
}

const KEEP: HTMLImageElement[] = [];

function preloadImage(src: string) {
  return new Promise<void>((res) => {
    const im = new Image();
    im.onload = () => im.decode().then(() => res(), () => res());
    im.onerror = () => res();
    im.src = src;
    KEEP.push(im);
  });
}

async function toDataUri(src: string): Promise<string | null> {
  try {
    const blob = await (await fetch(src)).blob();
    return await new Promise((res) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result));
      r.onerror = () => res(null);
      r.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
}

/** Loads textures (CSS masks don't block rendering) and depth maps; scenes render only when ready. */
export function useAssets(tl: Timeline): boolean {
  Object.assign(ART, tl.art ?? {});
  const [handle] = useState(() => delayRender("carregando texturas e mapas de profundidade"));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const tex = [
      ...[0, 1].map((k) => `fx/fog_${k}.png`),
      ...[0, 1, 2, 3, 4, 5, 6, 7].map((k) => `fx/grain_${k}.png`),
      ...[0, 1, 2].map((k) => `fx/brush_${k}.png`),
      ...[0, 1, 2, 3, 4].map((k) => `fx/splatter_${k}.png`),
      "fx/grunge.jpg",
      ...Array.from({ length: tl.images ?? 0 }, (_, i) => `art/bg_${i + 1}.jpg`),
    ];
    const depth = Object.entries(tl.art ?? {}).filter(([, a]) => a.depth);
    Promise.all([
      ...tex.map((p) => preloadImage(staticFile(p))),
      ...depth.map(async ([name]) => {
        const uri = await toDataUri(staticFile(`art/${name}_depth.png`));
        if (uri) DEPTH[name] = uri;
      }),
    ]).then(() => {
      setReady(true);
      continueRender(handle);
    });
    // once per page: the timeline (input props) does not change while a composition renders
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handle]);
  return ready;
}
