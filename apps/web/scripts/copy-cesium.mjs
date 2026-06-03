// Copy Cesium's static runtime assets into public/cesium so the browser can
// load Workers/Assets/Widgets at runtime (window.CESIUM_BASE_URL = '/cesium').
// Cesium's npm ESM build does not bundle these; they must be served statically.
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
console.log("[copy-cesium] done -> public/cesium");
