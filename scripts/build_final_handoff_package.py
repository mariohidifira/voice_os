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
ZIP_PATH = REPORTS_DIR / "final-handoff-bundle.zip"
MANIFEST_PATH = REPORTS_DIR / "final-handoff-bundle.manifest.json"

INCLUDED_PATHS = [
    "FINAL-HANDOFF-2026-08-25.md",
    "EXTERNAL-EXECUTION-CHECKLIST-2026-08-25.md",
    "scripts/check_phase4_remote_ready.ps1",
    "scripts/verify_phase4_remote_artifact.py",
    "scripts/check_phase5_external_delivery.py",
    "scripts/check_external_closeout_complete.py",
    "scripts/materialize_pending_external_reports.py",
    "scripts/refresh_final_handoff.py",
    "reports/final-handoff-summary.json",
    "reports/final-local-audit.json",
    "reports/final-refresh-status.json",
    "reports/external-execution-checklist.json",
    "reports/phase4-remote-artifact-verification.json",
    "reports/phase5-external-delivery.json",
    "reports/external-closeout-status.json",
    "PHASE-4-REPORT.md",
    "PHASE-4-REMOTE-RUNBOOK.md",
    "reports/phase4-evidence-summary.json",
    "reports/phase4-evidence-bundle.zip",
    "reports/phase4-evidence-bundle.manifest.json",
    "PHASE-5-REPORT.md",
    "PHASE-5-HOSTED-ASSET-RUNBOOK.md",
    "reports/phase5-hosted-asset-readiness.json",
    "reports/phase5-acceptance-summary.json",
    "reports/phase5-evidence-bundle.zip",
    "reports/phase5-evidence-bundle.manifest.json",
]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_manifest() -> dict[str, object]:
    included: list[dict[str, object]] = []
    missing: list[str] = []

    final_summary = json.loads(
        (REPO_ROOT / "reports" / "final-handoff-summary.json").read_text(encoding="utf-8")
    )

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
        "scope": "final_handoff_bundle",
        "bundle_path": "reports/final-handoff-bundle.zip",
        "included": included,
        "missing": missing,
        "project_completion_estimate_percent": final_summary.get(
            "project_completion_estimate_percent"
        ),
        "phase4_next_gap": final_summary.get("local_proven", {})
        .get("phase4", {})
        .get("next_gap"),
        "phase4_environment_blocker": final_summary.get("local_proven", {})
        .get("phase4", {})
        .get("environment_blocker"),
        "phase5_next_gap": final_summary.get("local_proven", {})
        .get("phase5", {})
        .get("next_gap"),
        "phase5_environment_blocker": final_summary.get("local_proven", {})
        .get("phase5", {})
        .get("environment_blocker"),
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
