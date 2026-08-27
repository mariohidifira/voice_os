import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(__dirname, "..");
const bundlePath = path.join(packageRoot, "dist", "voiceos.js");
const maxGzipBytes = 60 * 1024;

const bundle = await readFile(bundlePath);
const gzipBytes = gzipSync(bundle, { level: 9 }).byteLength;
const withinBudget = gzipBytes <= maxGzipBytes;

console.log(
  JSON.stringify(
    {
      scope: "widget_bundle_size_check",
      bundle: "packages/widget/dist/voiceos.js",
      bytes: bundle.byteLength,
      gzip_bytes: gzipBytes,
      gzip_budget_bytes: maxGzipBytes,
      within_budget,
    },
    null,
    2,
  ),
);

if (!withinBudget) {
  process.exitCode = 1;
}
