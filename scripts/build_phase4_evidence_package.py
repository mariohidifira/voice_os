"""Package Phase 4 evidence artifacts into a single ZIP bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

try:
    from scripts.deterministic_zip import write_deterministic_zip
except ModuleNotFoundError:
    from deterministic_zip import write_deterministic_zip

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
PACKAGE_PATH = REPORTS_DIR / "phase4-evidence-bundle.zip"
MANIFEST_PATH = REPORTS_DIR / "phase4-evidence-bundle.manifest.json"
TODAY = "2026-08-25"

FILES = [
    ROOT / "PHASE-4-REPORT.md",
    ROOT / "PHASE-4-REMOTE-RUNBOOK.md",
    ROOT / "scripts" / "check_phase4_remote_ready.ps1",
    ROOT / "scripts" / "verify_phase4_remote_artifact.py",
    ROOT / "reports" / "phase4-local-acceptance.json",
    ROOT / "reports" / "phase4-remote-readiness.json",
    ROOT / "reports" / "phase4-evidence-summary.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    included: list[dict[str, object]] = []
    missing: list[str] = []
    summary_path = ROOT / "reports" / "phase4-evidence-summary.json"
    next_gap = None
    environment_blocker = None
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        next_gap = summary.get("next_gap")
        environment_blocker = summary.get("local_acceptance", {}).get("environment_blocker")

    members: list[str] = []
    for path in FILES:
        rel = path.relative_to(ROOT).as_posix()
        if path.exists():
            members.append(rel)
            included.append(
                {
                    "path": rel,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        else:
            missing.append(rel)

    write_deterministic_zip(PACKAGE_PATH, ROOT, members)

    manifest = {
        "date": TODAY,
        "scope": "phase4_evidence_bundle",
        "bundle_path": PACKAGE_PATH.relative_to(ROOT).as_posix(),
        "included": included,
        "missing": missing,
        "bundle_bytes": PACKAGE_PATH.stat().st_size if PACKAGE_PATH.exists() else 0,
        "bundle_sha256": _sha256(PACKAGE_PATH) if PACKAGE_PATH.exists() else None,
        "next_gap": next_gap,
        "environment_blocker": environment_blocker,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
