"""Build a consolidated Phase 4 evidence summary from existing reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
LOCAL_REPORT = REPORTS_DIR / "phase4-local-acceptance.json"
REMOTE_REPORT = REPORTS_DIR / "phase4-remote-readiness.json"
SUMMARY_REPORT = REPORTS_DIR / "phase4-evidence-summary.json"
TODAY = "2026-08-25"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _step_counts(data: dict[str, Any]) -> dict[str, int]:
    steps = list(data.get("steps") or [])
    ok = sum(1 for step in steps if step.get("ok") is True)
    failed = sum(1 for step in steps if step.get("ok") is False)
    return {"total": len(steps), "ok": ok, "failed": failed}


def _environment_blocker(data: dict[str, Any]) -> dict[str, Any] | None:
    steps = list(data.get("steps") or [])
    for step in steps:
        blocker = step.get("environment_blocker")
        if isinstance(blocker, dict):
            return blocker
    return None


def main() -> int:
    local = _load_json(LOCAL_REPORT)
    remote = _load_json(REMOTE_REPORT)
    if local is None:
        raise FileNotFoundError(f"Missing required report: {LOCAL_REPORT}")

    remote_available = remote is not None

    summary = {
        "date": TODAY,
        "scope": "phase4_evidence_summary",
        "passed": bool(local.get("passed")) and bool(remote and remote.get("passed")),
        "local_acceptance": {
            "path": str(LOCAL_REPORT.relative_to(ROOT)).replace("\\", "/"),
            "available": True,
            "passed": bool(local.get("passed")),
            "server_readiness": dict(local.get("server_readiness") or {}),
            "step_counts": _step_counts(local),
            "environment_blocker": _environment_blocker(local),
        },
        "remote_readiness": {
            "path": str(REMOTE_REPORT.relative_to(ROOT)).replace("\\", "/"),
            "available": remote_available,
            "passed": bool(remote and remote.get("passed")),
            "repo": remote.get("repo") if remote else None,
            "step_counts": _step_counts(remote or {}),
        },
        "next_gap": (
            "remote_readiness_report_missing"
            if not remote_available
            else "remote_repo_access"
            if not remote.get("passed")
            else "provider_backed_latency_evidence"
        ),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
