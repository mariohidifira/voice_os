from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
STATUS_DATE = "2026-08-25"


def read_json(relative_path: str) -> dict[str, object] | None:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_if_missing(relative_path: str, payload: dict[str, object]) -> dict[str, object]:
    path = REPO_ROOT / relative_path
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("pending") is True and existing.get("passed") is not True:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return {
                "path": relative_path,
                "created": False,
                "refreshed_placeholder": True,
                "preserved_existing": False,
            }
        return {
            "path": relative_path,
            "created": False,
            "refreshed_placeholder": False,
            "preserved_existing": True,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {
        "path": relative_path,
        "created": True,
        "refreshed_placeholder": False,
        "preserved_existing": False,
    }


def main() -> int:
    phase4_summary = read_json("reports/phase4-evidence-summary.json") or {}
    phase5_hosted = read_json("reports/phase5-hosted-asset-readiness.json") or {}

    phase4_placeholder = {
        "scope": "phase4_remote_artifact_verification",
        "status_date": STATUS_DATE,
        "artifact_root": None,
        "passed": False,
        "pending": True,
        "current_gap": "phase4_remote_closeout_pending",
        "detail": "Awaiting first successful external GitHub Actions artifact capture for Phase 4.",
        "expected_input": {
            "artifact_source": "GitHub Actions nightly workflow artifact",
            "verifier_command": "python scripts/verify_phase4_remote_artifact.py <artifact_dir>",
            "output_report": "reports/phase4-remote-artifact-verification.json",
        },
        "local_reference": {
            "phase4_next_gap": phase4_summary.get("next_gap"),
            "environment_blocker": (phase4_summary.get("local_acceptance") or {}).get(
                "environment_blocker"
            )
            if isinstance(phase4_summary.get("local_acceptance"), dict)
            else None,
        },
    }
    phase5_placeholder = {
        "scope": "phase5_external_delivery",
        "status_date": STATUS_DATE,
        "base_url": None,
        "asset_url": None,
        "passed": False,
        "pending": True,
        "current_gap": "phase5_external_closeout_pending",
        "detail": "Awaiting externally hosted widget delivery verification outside this executor.",
        "expected_input": {
            "verifier_command": "python scripts/check_phase5_external_delivery.py --base-url https://<host> --expected-host <domain>",
            "output_report": "reports/phase5-external-delivery.json",
        },
        "local_reference": {
            "phase5_next_gap": phase5_hosted.get("next_gap"),
            "environment_blocker": phase5_hosted.get("environment_blocker"),
        },
    }

    results = [
        write_if_missing("reports/phase4-remote-artifact-verification.json", phase4_placeholder),
        write_if_missing("reports/phase5-external-delivery.json", phase5_placeholder),
    ]
    report = {
        "scope": "materialize_pending_external_reports",
        "status_date": STATUS_DATE,
        "results": results,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
