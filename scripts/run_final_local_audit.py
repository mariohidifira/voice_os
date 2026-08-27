from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "reports" / "final-local-audit.json"
SCRIPTS_DIR = REPO_ROOT / "scripts"
PYTEST_BASETEMP = REPO_ROOT / ".pytest-tmp" / "final-local-audit"
BASE_PROJECT_COMPLETION_ESTIMATE_PERCENT = 93
SANITIZED_JSON_STEPS = {
    "phase4_evidence_summary": "[phase4 evidence summary output omitted; see parsed]",
    "phase4_evidence_verify": "[phase4 evidence verification output omitted; see parsed]",
    "phase5_asset_ready": "[phase5 hosted-asset readiness output omitted; see parsed]",
    "phase5_acceptance": "[phase5 acceptance output omitted; see parsed]",
    "phase5_evidence_verify": "[phase5 evidence verification output omitted; see parsed]",
    "external_execution_checklist": "[external execution checklist output omitted; see parsed]",
    "external_closeout_status": "[external closeout status output omitted; see parsed]",
}


def _summarize_parsed(name: str, parsed: dict[str, object]) -> dict[str, object]:
    if name == "phase4_evidence_summary":
        local_acceptance = parsed.get("local_acceptance")
        remote_readiness = parsed.get("remote_readiness")
        return {
            "scope": parsed.get("scope"),
            "date": parsed.get("date"),
            "passed": parsed.get("passed"),
            "next_gap": parsed.get("next_gap"),
            "local_acceptance_passed": local_acceptance.get("passed")
            if isinstance(local_acceptance, dict)
            else None,
            "environment_blocker": local_acceptance.get("environment_blocker")
            if isinstance(local_acceptance, dict)
            else None,
            "remote_readiness_passed": remote_readiness.get("passed")
            if isinstance(remote_readiness, dict)
            else None,
            "remote_repo": remote_readiness.get("repo")
            if isinstance(remote_readiness, dict)
            else None,
        }
    if name == "phase4_evidence_verify":
        return {
            "scope": parsed.get("scope"),
            "bundle_path": parsed.get("bundle_path"),
            "bundle_exists": parsed.get("bundle_exists"),
            "bundle_sha256_ok": parsed.get("bundle_sha256_ok"),
            "missing_entries": parsed.get("missing_entries"),
            "failed_entries": parsed.get("failed_entries"),
            "passed": parsed.get("passed"),
        }
    if name == "phase5_asset_ready":
        steps = parsed.get("steps")
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "passed": parsed.get("passed"),
            "next_gap": parsed.get("next_gap"),
            "environment_blocker": parsed.get("environment_blocker"),
            "artifacts": parsed.get("artifacts"),
            "step_count": len(steps) if isinstance(steps, list) else None,
        }
    if name == "phase5_acceptance":
        steps = parsed.get("steps")
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "passed": parsed.get("passed"),
            "pending": parsed.get("pending"),
            "hosted_asset_next_gap": parsed.get("hosted_asset_next_gap"),
            "environment_blocker": parsed.get("environment_blocker"),
            "pytest_widget_origin": parsed.get("pytest_widget_origin"),
            "step_count": len(steps) if isinstance(steps, list) else None,
        }
    if name == "external_execution_checklist":
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "artifacts": parsed.get("artifacts"),
            "phase4_current_gap": (parsed.get("phase4") or {}).get("current_gap")
            if isinstance(parsed.get("phase4"), dict)
            else None,
            "phase5_current_gap": (parsed.get("phase5") or {}).get("current_gap")
            if isinstance(parsed.get("phase5"), dict)
            else None,
            "project_completion_estimate_percent": (parsed.get("global") or {}).get(
                "project_completion_estimate_percent"
            )
            if isinstance(parsed.get("global"), dict)
            else None,
        }
    if name == "external_closeout_status":
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "project_completion_estimate_percent": parsed.get(
                "project_completion_estimate_percent"
            ),
            "complete": parsed.get("complete"),
            "remaining_gaps": parsed.get("remaining_gaps"),
        }
    return parsed


def run_step(name: str, command: list[str]) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": " ".join(command),
        "output": output,
    }


def python_step(name: str, script_name: str) -> dict[str, object]:
    return run_step(name, [sys.executable, str(SCRIPTS_DIR / script_name)])


def parse_json_output(step: dict[str, object]) -> dict[str, object] | None:
    output = str(step.get("output") or "").strip()
    if not output:
        return None
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None


def sanitize_step(step: dict[str, object]) -> None:
    name = str(step.get("name") or "")
    if name == "pytest_suite" and bool(step.get("ok")):
        step["output"] = "[pytest output omitted on success]"
        return
    if (
        name in SANITIZED_JSON_STEPS
        and isinstance(step.get("parsed"), dict)
        and (bool(step.get("ok")) or name in {"phase5_asset_ready", "external_closeout_status"})
    ):
        step["parsed"] = _summarize_parsed(name, step["parsed"])
        step["output"] = SANITIZED_JSON_STEPS[name]
        return


def main() -> int:
    PYTEST_BASETEMP.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        run_step(
            "pytest_suite",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(PYTEST_BASETEMP),
            ],
        ),
        python_step("phase4_evidence_summary", "build_phase4_evidence_summary.py"),
        python_step("phase4_evidence_verify", "verify_phase4_evidence_package.py"),
        python_step("phase5_asset_ready", "check_phase5_hosted_asset_ready.py"),
        python_step("phase5_acceptance", "check_phase5_acceptance.py"),
        python_step("phase5_evidence_verify", "verify_phase5_evidence_package.py"),
        python_step("materialize_pending_external_reports", "materialize_pending_external_reports.py"),
        python_step("external_execution_checklist", "build_external_execution_checklist.py"),
        python_step("external_closeout_status", "check_external_closeout_complete.py"),
    ]

    for step in steps:
        payload = parse_json_output(step)
        if payload is not None:
            step["parsed"] = payload
        sanitize_step(step)

    for step in steps:
        if step["name"] == "phase5_asset_ready":
            payload = step.get("parsed") or {}
            step["ok_local"] = (
                isinstance(payload, dict)
                and payload.get("next_gap") == "widget_bundle_not_built_in_executor"
            ) or bool(step["ok"])
            if not step["ok"]:
                step["expected_external_gap"] = "widget_bundle_not_built_in_executor"
        elif step["name"] == "external_closeout_status":
            payload = step.get("parsed") or {}
            remaining = payload.get("remaining_gaps") if isinstance(payload, dict) else None
            expected = {
                "phase4_remote_closeout_pending",
                "phase5_external_closeout_pending",
            }
            step["ok_local"] = (
                isinstance(remaining, list) and set(str(item) for item in remaining) == expected
            ) or bool(step["ok"])
            step["expected_external_gaps"] = sorted(expected)
        else:
            step["ok_local"] = bool(step["ok"])

    phase4_summary = json.loads(
        (REPO_ROOT / "reports" / "phase4-evidence-summary.json").read_text(encoding="utf-8")
    )
    phase5_acceptance = json.loads(
        (REPO_ROOT / "reports" / "phase5-acceptance-summary.json").read_text(encoding="utf-8")
    )
    phase5_hosted = json.loads(
        (REPO_ROOT / "reports" / "phase5-hosted-asset-readiness.json").read_text(encoding="utf-8")
    )
    final_summary_path = REPO_ROOT / "reports" / "final-handoff-summary.json"
    completion_estimate = BASE_PROJECT_COMPLETION_ESTIMATE_PERCENT + (
        2 if phase5_hosted.get("passed") is True else 0
    )
    expected_external_gaps = [
        phase4_summary.get("next_gap"),
        phase5_hosted.get("next_gap"),
        "phase4_remote_closeout_pending",
        "phase5_external_closeout_pending",
    ]

    report = {
        "scope": "final_local_audit",
        "status_date": "2026-08-25",
        "passed": all(bool(step["ok_local"]) for step in steps),
        "project_completion_estimate_percent": completion_estimate,
        "phase4_next_gap": phase4_summary.get("next_gap"),
        "phase4_environment_blocker": phase4_summary.get("local_acceptance", {}).get(
            "environment_blocker"
        ),
        "phase5_next_gap": phase5_hosted.get("next_gap"),
        "phase5_environment_blocker": phase5_hosted.get("environment_blocker"),
        "phase5_acceptance_passed": phase5_acceptance.get("passed"),
        "final_handoff_summary_present": final_summary_path.is_file(),
        "expected_external_gaps": [gap for gap in expected_external_gaps if gap],
        "steps": steps,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
