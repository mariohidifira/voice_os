from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:
    from scripts.deterministic_zip import write_deterministic_zip
except ModuleNotFoundError:
    from deterministic_zip import write_deterministic_zip

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
ZIP_PATH = REPORTS_DIR / "phase5-evidence-bundle.zip"
MANIFEST_PATH = REPORTS_DIR / "phase5-evidence-bundle.manifest.json"

INCLUDED_PATHS = [
    "PHASE-5-REPORT.md",
    "PHASE-5-HOSTED-ASSET-RUNBOOK.md",
    "FINAL-HANDOFF-2026-08-25.md",
    "packages/widget/README.md",
    "packages/widget/examples/host-page.html",
    "apps/web/lib/dashboard-phase5.ts",
    "apps/web/lib/dashboard-phase5.test.ts",
    "apps/web/public/voiceos.js",
    "packages/widget/dist/voiceos.js",
    "packages/widget/dist/size.json",
    "scripts/build_widget_bundle_fallback.py",
    "scripts/check_phase5_hosted_asset_ready.py",
    "scripts/check_phase5_acceptance.py",
    "scripts/check_phase5_external_delivery.py",
    "reports/phase5-hosted-asset-readiness.json",
    "reports/phase5-acceptance-summary.json",
    "reports/final-handoff-summary.json",
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_manifest() -> dict[str, object]:
    included: list[dict[str, object]] = []
    missing: list[str] = []
    next_gap = None
    environment_blocker = None

    readiness_path = REPO_ROOT / "reports" / "phase5-hosted-asset-readiness.json"
    if readiness_path.is_file():
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        next_gap = readiness.get("next_gap")
        environment_blocker = readiness.get("environment_blocker")

    for relative_path in INCLUDED_PATHS:
        absolute_path = REPO_ROOT / relative_path
        if not absolute_path.is_file():
            missing.append(relative_path)
            continue
        payload = absolute_path.read_bytes()
        included.append(
            {
                "path": relative_path,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )

    return {
        "scope": "phase5_evidence_bundle",
        "bundle_path": "reports/phase5-evidence-bundle.zip",
        "included": included,
        "missing": missing,
        "next_gap": next_gap,
        "environment_blocker": environment_blocker,
    }


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()

    write_deterministic_zip(
        ZIP_PATH,
        REPO_ROOT,
        [str(item["path"]) for item in manifest["included"]],
    )

    bundle_bytes = ZIP_PATH.read_bytes()
    manifest["bundle_bytes"] = len(bundle_bytes)
    manifest["bundle_sha256"] = sha256_bytes(bundle_bytes)

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if not manifest["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
