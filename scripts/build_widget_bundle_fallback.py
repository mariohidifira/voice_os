from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = REPO_ROOT / "packages" / "widget" / "src" / "index.ts"
ESBUILD_PATH = REPO_ROOT / "node_modules" / "@esbuild" / "win32-x64" / "esbuild.exe"
DIST_DIR = REPO_ROOT / "packages" / "widget" / "dist"
BUNDLE_PATH = DIST_DIR / "voiceos.js"
SIZE_PATH = DIST_DIR / "size.json"
HOSTED_PATH = REPO_ROOT / "apps" / "web" / "public" / "voiceos.js"
MAX_GZIP_BYTES = 60 * 1024


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    if not ESBUILD_PATH.is_file():
        raise SystemExit(
            "Native esbuild binary is missing. Run npm install before using the fallback."
        )

    source = SOURCE_PATH.read_bytes()
    command = [
        str(ESBUILD_PATH),
        "--loader=ts",
        "--bundle",
        "--format=esm",
        "--platform=browser",
        "--target=es2020",
        "--minify",
        "--legal-comments=none",
        "--sourcefile=packages/widget/src/index.ts",
    ]
    completed = subprocess.run(
        command,
        input=source,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        error = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"Native esbuild fallback failed: {error}")

    bundle = completed.stdout
    gzip_bytes = len(gzip.compress(bundle, compresslevel=9, mtime=0))
    if gzip_bytes > MAX_GZIP_BYTES:
        raise SystemExit(
            f"voiceos.js gzip size {gzip_bytes} bytes exceeds budget {MAX_GZIP_BYTES} bytes"
        )

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    HOSTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_PATH.write_bytes(bundle)
    HOSTED_PATH.write_bytes(bundle)

    size_payload = {
        "build_method": "esbuild_native_stdin_fallback",
        "source_sha256": sha256(source),
        "browser_bundle": {
            "path": "dist/voiceos.js",
            "bytes": len(bundle),
            "gzip_bytes": gzip_bytes,
            "gzip_budget_bytes": MAX_GZIP_BYTES,
            "sha256": sha256(bundle),
        },
        "hosted_asset": {
            "path": "apps/web/public/voiceos.js",
            "bytes": len(bundle),
            "sha256": sha256(bundle),
        },
    }
    SIZE_PATH.write_text(json.dumps(size_payload, indent=2) + "\n", encoding="utf-8")

    report = {
        "scope": "widget_browser_bundle_fallback",
        "build_method": size_payload["build_method"],
        "browser_bundle": "packages/widget/dist/voiceos.js",
        "hosted_asset": "apps/web/public/voiceos.js",
        "size_artifact": "packages/widget/dist/size.json",
        "bytes": len(bundle),
        "gzip_bytes": gzip_bytes,
        "gzip_budget_bytes": MAX_GZIP_BYTES,
        "within_budget": True,
        "sha256": sha256(bundle),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
