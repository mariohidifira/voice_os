from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "reports" / "final-refresh-status.json"
SCRIPTS_DIR = REPO_ROOT / "scripts"
SANITIZED_JSON_STEPS = {
    "phase4_evidence_package": "[phase4 evidence package output omitted; see parsed]",
    "phase4_evidence_verify": "[phase4 evidence verification output omitted; see parsed]",
    "final_handoff_summary": "[final handoff summary output omitted; see parsed]",
    "phase5_evidence_package": "[phase5 evidence package output omitted; see parsed]",
    "phase5_evidence_verify": "[phase5 evidence verification output omitted; see parsed]",
    "final_external_checklist": "[external execution checklist output omitted; see parsed]",
    "final_external_closeout": "[external closeout status output omitted; see parsed]",
}


def _summarize_parsed(name: str, parsed: dict[str, object]) -> dict[str, object]:
    if name in {"phase4_evidence_package", "phase5_evidence_package"}:
        included = parsed.get("included")
        if not isinstance(included, list):
            included_count = parsed.get("included_count")
        else:
            included_count = len(included)
        return {
            "scope": parsed.get("scope"),
            "bundle_path": parsed.get("bundle_path"),
            "bundle_bytes": parsed.get("bundle_bytes"),
            "bundle_sha256": parsed.get("bundle_sha256"),
            "missing": parsed.get("missing"),
            "next_gap": parsed.get("next_gap"),
            "included_count": included_count,
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
    if name == "final_handoff_summary":
        external_pending = parsed.get("external_pending")
        if not isinstance(external_pending, list):
            external_pending_count = parsed.get("external_pending_count")
        else:
            external_pending_count = len(external_pending)
        evidence_files = parsed.get("evidence_files")
        if not isinstance(evidence_files, list):
            evidence_files_count = parsed.get("evidence_files_count")
        else:
            evidence_files_count = len(evidence_files)
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "project_completion_estimate_percent": parsed.get(
                "project_completion_estimate_percent"
            ),
            "local_proven": parsed.get("local_proven"),
            "external_pending_count": external_pending_count,
            "pending_external_reports": parsed.get("pending_external_reports"),
            "evidence_files_count": evidence_files_count,
        }
    if name == "final_external_checklist":
        phase4 = parsed.get("phase4")
        phase5 = parsed.get("phase5")
        global_section = parsed.get("global")
        return {
            "scope": parsed.get("scope"),
            "status_date": parsed.get("status_date"),
            "artifacts": parsed.get("artifacts"),
            "phase4_current_gap": phase4.get("current_gap")
            if isinstance(phase4, dict)
            else parsed.get("phase4_current_gap"),
            "phase4_environment_blocker": phase4.get("environment_blocker")
            if isinstance(phase4, dict)
            else parsed.get("phase4_environment_blocker"),
            "phase5_current_gap": phase5.get("current_gap")
            if isinstance(phase5, dict)
            else parsed.get("phase5_current_gap"),
            "phase5_environment_blocker": phase5.get("environment_blocker")
            if isinstance(phase5, dict)
            else parsed.get("phase5_environment_blocker"),
            "project_completion_estimate_percent": global_section.get(
                "project_completion_estimate_percent"
            )
            if isinstance(global_section, dict)
            else parsed.get("project_completion_estimate_percent"),
        }
    if name == "final_external_closeout":
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
    if name in SANITIZED_JSON_STEPS and isinstance(step.get("parsed"), dict):
        step["parsed"] = _summarize_parsed(name, step["parsed"])
        step["output"] = SANITIZED_JSON_STEPS[name]
        return
    if name == "final_local_audit" and bool(step.get("ok")):
        parsed = step.get("parsed")
        if isinstance(parsed, dict):
            preserved = {
                key: parsed.get(key)
                for key in (
                    "scope",
                    "status_date",
                    "passed",
                    "project_completion_estimate_percent",
                    "phase4_next_gap",
                    "phase4_environment_blocker",
                    "phase5_next_gap",
                    "phase5_environment_blocker",
                    "phase5_acceptance_passed",
                    "final_handoff_summary_present",
                    "expected_external_gaps",
                )
                if key in parsed
            }
            step["parsed"] = preserved
        step["output"] = "[final local audit output omitted on success]"
        return
    if name not in {
        "final_handoff_package_final",
        "final_handoff_verify_final",
    }:
        return
    parsed = step.get("parsed")
    if isinstance(parsed, dict):
        preserved = {
            key: parsed.get(key)
            for key in (
                "scope",
                "bundle_path",
                "bundle_exists",
                "manifest_exists",
                "missing",
                "missing_entries",
                "failed_entries",
                "passed",
                "project_completion_estimate_percent",
                "phase4_next_gap",
                "phase5_next_gap",
            )
            if key in parsed
        }
        step["parsed"] = preserved
    step["output"] = "[sanitized final handoff package details]"


def normalize_steps(steps: list[dict[str, object]]) -> None:
    for step in steps:
        payload = parse_json_output(step)
        if payload is not None:
            step["parsed"] = payload
        sanitize_step(step)

    for step in steps:
        if step["name"] == "final_external_closeout":
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


def build_report(steps: list[dict[str, object]], *, finalized: bool) -> dict[str, object]:
    return {
        "scope": "final_refresh_status",
        "status_date": "2026-08-25",
        "finalized": finalized,
        "passed": all(bool(step["ok_local"]) for step in steps),
        "steps": steps,
    }


def write_report(steps: list[dict[str, object]], *, finalized: bool) -> dict[str, object]:
    normalize_steps(steps)
    report = build_report(steps, finalized=finalized)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    steps: list[dict[str, object]] = [
        python_step("phase4_evidence_package", "build_phase4_evidence_package.py"),
        python_step("phase4_evidence_verify", "verify_phase4_evidence_package.py"),
        python_step("final_local_audit", "run_final_local_audit.py"),
        python_step("final_handoff_summary", "build_final_handoff_summary.py"),
        python_step("phase5_evidence_package", "build_phase5_evidence_package.py"),
        python_step("phase5_evidence_verify", "verify_phase5_evidence_package.py"),
        python_step("materialize_pending_external_reports", "materialize_pending_external_reports.py"),
        python_step("final_external_checklist", "build_external_execution_checklist.py"),
        python_step("final_external_closeout", "check_external_closeout_complete.py"),
    ]
    write_report(steps, finalized=True)

    runtime_steps = steps + [
        python_step("final_handoff_package_final", "build_final_handoff_package.py"),
        python_step("final_handoff_verify_final", "verify_final_handoff_package.py"),
    ]
    normalize_steps(runtime_steps)
    report = build_report(runtime_steps, finalized=True)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
