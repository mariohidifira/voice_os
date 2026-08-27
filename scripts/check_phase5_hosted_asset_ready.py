from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def step(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"name": name, "ok": ok, "detail": detail}


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def environment_blocker(
    *,
    browser_bundle_present: bool,
    hosted_asset_present: bool,
    size_artifact_present: bool,
) -> dict[str, object] | None:
    if browser_bundle_present and hosted_asset_present and size_artifact_present:
        return None
    missing_artifacts: list[str] = []
    if not browser_bundle_present:
        missing_artifacts.append("packages/widget/dist/voiceos.js")
    if not hosted_asset_present:
        missing_artifacts.append("apps/web/public/voiceos.js")
    if not size_artifact_present:
        missing_artifacts.append("packages/widget/dist/size.json")
    return {
        "type": "widget_bundle_not_built_in_executor",
        "detail": "Required generated widget bundle artifacts are absent in this executor",
        "missing_artifacts": missing_artifacts,
    }


def main() -> int:
    dashboard_helper = read_text("apps/web/lib/dashboard-phase5.ts")
    web_package = json.loads(read_text("apps/web/package.json"))
    widget_package = json.loads(read_text("packages/widget/package.json"))
    widget_build = read_text("packages/widget/scripts/build-browser.mjs")
    widget_example = read_text("packages/widget/examples/host-page.html")
    widget_readme = read_text("packages/widget/README.md")

    public_dir = REPO_ROOT / "apps" / "web" / "public"
    hosted_asset = public_dir / "voiceos.js"
    browser_bundle = REPO_ROOT / "packages" / "widget" / "dist" / "voiceos.js"
    size_artifact = REPO_ROOT / "packages" / "widget" / "dist" / "size.json"

    steps = [
        step(
            "dashboard_snippet_hosted_path",
            'src="${options.hostOrigin}/voiceos.js"' in dashboard_helper,
            "dashboard embed snippet should point to /voiceos.js on the same host origin",
        ),
        step(
            "dashboard_prebuild_widget_bundle",
            web_package.get("scripts", {}).get("prebuild")
            == "npm run build --workspace=@voiceos/web",
            "dashboard build should invoke the widget build first",
        ),
        step(
            "widget_build_generates_hosted_asset",
            '"build": "tsc && node ./scripts/build-browser.mjs"' in read_text(
                "packages/widget/package.json"
            )
            and 'path.join(webPublicDir, "voiceos.js")' in widget_build,
            "widget build should generate the browser bundle and sync it to apps/web/public/voiceos.js",
        ),
        step(
            "widget_size_budget_enforced",
            'const maxGzipBytes = 60 * 1024;' in widget_build
            and '"size": "node ./scripts/check-size.mjs"' in read_text("packages/widget/package.json"),
            "widget build should enforce the <= 60 KB gzip budget and expose a size check command",
        ),
        step(
            "host_page_uses_browser_bundle",
            "../dist/voiceos.js" in widget_example,
            "host-page example should reference the generated browser bundle",
        ),
        step(
            "widget_docs_describe_hosted_asset",
            "apps/web/public/voiceos.js" in widget_readme
            and "npm run size --workspace=@voiceos/web" in widget_readme,
            "widget README should document the hosted asset path and size validation command",
        ),
        step(
            "public_directory_present",
            public_dir.is_dir(),
            "apps/web/public should exist as the target directory for the hosted widget asset",
        ),
        step(
            "browser_bundle_present",
            browser_bundle.is_file(),
            "packages/widget/dist/voiceos.js should exist after a successful widget build",
        ),
        step(
            "hosted_asset_present",
            hosted_asset.is_file(),
            "apps/web/public/voiceos.js should exist after a successful widget build",
        ),
        step(
            "size_artifact_present",
            size_artifact.is_file(),
            "packages/widget/dist/size.json should exist after a successful widget build",
        ),
        step(
            "widget_package_declares_esbuild",
            widget_package.get("devDependencies", {}).get("esbuild") == "^0.28.2",
            "widget workspace should declare esbuild for the browser bundle step",
        ),
    ]

    if hosted_asset.is_file() and browser_bundle.is_file() and size_artifact.is_file():
        bundle_bytes = browser_bundle.read_bytes()
        hosted_bytes = hosted_asset.read_bytes()
        try:
            size_payload = json.loads(size_artifact.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            size_payload = {}
        browser_metadata = size_payload.get("browser_bundle", {})
        hosted_metadata = size_payload.get("hosted_asset", {})
        gzip_bytes = len(gzip.compress(bundle_bytes, compresslevel=9, mtime=0))
        bundle_hash = sha256(bundle_bytes)
        steps.extend(
            [
                step(
                    "browser_and_hosted_assets_match",
                    bundle_bytes == hosted_bytes,
                    "dist/voiceos.js and apps/web/public/voiceos.js should be byte-identical",
                ),
                step(
                    "size_metadata_matches_bundle",
                    isinstance(browser_metadata, dict)
                    and browser_metadata.get("bytes") == len(bundle_bytes)
                    and browser_metadata.get("gzip_bytes") == gzip_bytes
                    and browser_metadata.get("gzip_budget_bytes") == 60 * 1024,
                    "size.json should match the generated bundle bytes and deterministic gzip size",
                ),
                step(
                    "bundle_hashes_match",
                    isinstance(browser_metadata, dict)
                    and isinstance(hosted_metadata, dict)
                    and browser_metadata.get("sha256") == bundle_hash
                    and hosted_metadata.get("sha256") == bundle_hash,
                    "size.json should carry the SHA-256 shared by dist and hosted assets",
                ),
                step(
                    "materialized_bundle_within_budget",
                    gzip_bytes <= 60 * 1024,
                    "the materialized browser bundle should stay within the <= 60 KB gzip budget",
                ),
            ]
        )

    passed = all(item["ok"] for item in steps)
    next_gap = None
    blocker = None
    if not passed:
        if (
            not browser_bundle.is_file()
            or not hosted_asset.is_file()
            or not size_artifact.is_file()
        ):
            next_gap = "widget_bundle_not_built_in_executor"
            blocker = environment_blocker(
                browser_bundle_present=browser_bundle.is_file(),
                hosted_asset_present=hosted_asset.is_file(),
                size_artifact_present=size_artifact.is_file(),
            )
        else:
            next_gap = "phase5_hosted_asset_contract_drift"

    report = {
        "scope": "phase5_hosted_asset_readiness",
        "status_date": "2026-08-25",
        "passed": passed,
        "next_gap": next_gap,
        "environment_blocker": blocker,
        "artifacts": {
            "public_directory": "apps/web/public",
            "browser_bundle": "packages/widget/dist/voiceos.js",
            "hosted_asset": "apps/web/public/voiceos.js",
            "size_artifact": "packages/widget/dist/size.json",
        },
        "steps": steps,
    }

    output_path = REPO_ROOT / "reports" / "phase5-hosted-asset-readiness.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
