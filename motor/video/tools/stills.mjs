// Render many stills with a single bundle:
// node tools/stills.mjs --comp Main --props <timeline.json> --public <dir> --out <dir> <frame> [frame...]
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const opt = {};
const frames = [];
for (let i = 0; i < args.length; i++) {
  if (args[i].startsWith("--")) opt[args[i].slice(2)] = args[++i];
  else frames.push(Number(args[i]));
}
const inputProps = JSON.parse(fs.readFileSync(opt.props, "utf8"));
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts"), publicDir: path.resolve(opt.public) });
const composition = await selectComposition({ serveUrl, id: opt.comp, inputProps });
for (const f of frames) {
  const output = path.join(opt.out, `${String(f).padStart(5, "0")}.jpg`);
  await renderStill({ composition, serveUrl, output, frame: f, imageFormat: "jpeg", jpegQuality: 90, inputProps });
  console.log(output);
}
