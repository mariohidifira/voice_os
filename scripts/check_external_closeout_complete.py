from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "external-closeout-status.json"
STATUS_DATE = "2026-08-25"


def read_json_if_present(relative_path: str) -> dict[str, object] | None:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def step(name: str, ok: bool, detail: str, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"name": name, "ok": ok, "detail": detail}
    payload.update(extra)
    return payload


def main() -> int:
    phase4_remote = read_json_if_present("reports/phase4-remote-artifact-verification.json")
    phase5_external = read_json_if_present("reports/phase5-external-delivery.json")
    final_summary = read_json_if_present("reports/final-handoff-summary.json") or {}

    phase4_steps = [
        step(
            "phase4_remote_report_present",
            phase4_remote is not None,
            "Phase 4 remote artifact verification report should exist",
            report="reports/phase4-remote-artifact-verification.json",
        ),
        step(
            "phase4_remote_report_passed",
            bool(phase4_remote and phase4_remote.get("passed") is True),
            "Phase 4 remote artifact verification should report passed=true",
            report="reports/phase4-remote-artifact-verification.json",
        ),
    ]

    phase5_steps = [
        step(
            "phase5_external_report_present",
            phase5_external is not None,
            "Phase 5 external delivery report should exist",
            report="reports/phase5-external-delivery.json",
        ),
        step(
            "phase5_external_report_passed",
            bool(phase5_external and phase5_external.get("passed") is True),
            "Phase 5 external delivery verification should report passed=true",
            report="reports/phase5-external-delivery.json",
        ),
    ]

    phase4_complete = all(item["ok"] for item in phase4_steps)
    phase5_complete = all(item["ok"] for item in phase5_steps)
    complete = phase4_complete and phase5_complete

    remaining_gaps: list[str] = []
    if not phase4_complete:
        remaining_gaps.append("phase4_remote_closeout_pending")
    if not phase5_complete:
        remaining_gaps.append("phase5_external_closeout_pending")

    report = {
        "scope": "external_closeout_status",
        "status_date": STATUS_DATE,
        "project_completion_estimate_percent": (
            100
            if complete
            else final_summary.get("project_completion_estimate_percent")
        ),
        "complete": complete,
        "remaining_gaps": remaining_gaps,
        "phase4": {
            "complete": phase4_complete,
            "steps": phase4_steps,
            "report": phase4_remote,
        },
        "phase5": {
            "complete": phase5_complete,
            "steps": phase5_steps,
            "report": phase5_external,
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
