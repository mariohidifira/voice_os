import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

import { build } from "esbuild";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(packageRoot, "..", "..");
const distDir = path.join(packageRoot, "dist");
const browserOutfile = path.join(distDir, "voiceos.js");
const webPublicDir = path.join(repoRoot, "apps", "web", "public");
const hostedOutfile = path.join(webPublicDir, "voiceos.js");
const maxGzipBytes = 60 * 1024;

await mkdir(distDir, { recursive: true });
await mkdir(webPublicDir, { recursive: true });

await build({
  entryPoints: [path.join(packageRoot, "src", "index.ts")],
  outfile: browserOutfile,
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2020"],
  minify: true,
  sourcemap: false,
  legalComments: "none",
});

const browserBundle = await readFile(browserOutfile);
const gzipBytes = gzipSync(browserBundle, { level: 9 }).byteLength;
const bundleSha256 = createHash("sha256").update(browserBundle).digest("hex");
if (gzipBytes > maxGzipBytes) {
  throw new Error(
    `voiceos.js gzip size ${gzipBytes} bytes exceeds budget ${maxGzipBytes} bytes`,
  );
}

await writeFile(hostedOutfile, browserBundle);
await writeFile(
  path.join(distDir, "size.json"),
  JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      browser_bundle: {
        path: "dist/voiceos.js",
        bytes: browserBundle.byteLength,
        gzip_bytes: gzipBytes,
        gzip_budget_bytes: maxGzipBytes,
        sha256: bundleSha256,
      },
      hosted_asset: {
        path: "apps/web/public/voiceos.js",
        bytes: browserBundle.byteLength,
        sha256: bundleSha256,
      },
    },
    null,
    2,
  ) + "\n",
);

console.log(
  JSON.stringify(
    {
      scope: "widget_browser_bundle",
      browser_bundle: path.relative(repoRoot, browserOutfile).replaceAll("\\", "/"),
      hosted_asset: path.relative(repoRoot, hostedOutfile).replaceAll("\\", "/"),
      bytes: browserBundle.byteLength,
      gzip_bytes: gzipBytes,
      gzip_budget_bytes: maxGzipBytes,
      within_budget: true,
    },
    null,
    2,
  ),
);
