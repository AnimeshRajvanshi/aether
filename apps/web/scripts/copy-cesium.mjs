// Copy Cesium's prebuilt UMD bundle + static runtime assets into public/cesium.
// We load Cesium as an external script (window.Cesium) rather than bundling it:
// Next's SWC minifier mis-compiles Cesium's bundled third-party code into an
// invalid chunk ("octal escape sequences are not allowed in template strings").
// Serving the prebuilt Cesium.js sidesteps the bundler entirely.
// Runs in predev/prebuild. Idempotent — skips if already present and non-empty.
import { cp, mkdir, readdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, "..");
const src = join(webRoot, "node_modules", "cesium", "Build", "Cesium");
const dest = join(webRoot, "public", "cesium");
const SUBDIRS = ["Workers", "Assets", "Widgets", "ThirdParty"];

async function exists(p) {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

async function nonEmpty(p) {
  try {
    return (await readdir(p)).length > 0;
  } catch {
    return false;
  }
}

if (!(await exists(src))) {
  console.error(
    `[copy-cesium] Cesium build not found at ${src}.\n` +
      "Run `pnpm install` first so node_modules/cesium exists.",
  );
  process.exit(1);
}

if (await nonEmpty(dest)) {
  console.log("[copy-cesium] public/cesium already populated — skipping.");
  process.exit(0);
}

await mkdir(dest, { recursive: true });
for (const sub of SUBDIRS) {
  const from = join(src, sub);
  if (await exists(from)) {
    await cp(from, join(dest, sub), { recursive: true });
    console.log(`[copy-cesium] copied ${sub}`);
  }
}
await cp(join(src, "Cesium.js"), join(dest, "Cesium.js"));
console.log("[copy-cesium] copied Cesium.js (UMD)");
console.log("[copy-cesium] done -> public/cesium");
