from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "reports" / "phase5-acceptance-summary.json"


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def step(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"name": name, "ok": ok, "detail": detail}


def run_pytest_widget_origin() -> tuple[bool, str]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        str(REPO_ROOT / "tests" / "test_api.py"),
        "-k",
        "public_widget_session_requires_valid_origin_and_public_key",
    ]
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
    return completed.returncode == 0, output


def main() -> int:
    readiness_path = REPO_ROOT / "reports" / "phase5-hosted-asset-readiness.json"
    readiness = (
        json.loads(readiness_path.read_text(encoding="utf-8"))
        if readiness_path.is_file()
        else {"passed": False, "next_gap": "phase5_hosted_asset_readiness_missing", "steps": []}
    )

    dashboard_helper = read_text("apps/web/lib/dashboard-phase5.ts")
    widget_readme = read_text("packages/widget/README.md")
    widget_example = read_text("packages/widget/examples/host-page.html")

    pytest_ok, pytest_output = run_pytest_widget_origin()

    steps = [
        step(
            "static_host_example_present",
            "../dist/voiceos.js" in widget_example,
            "the static host example should reference the generated browser bundle",
        ),
        step(
            "react_example_present",
            'import { VoiceOSWidget } from "@voiceos/web";' in widget_readme
            and "widget.mount();" in widget_readme,
            "the widget README should include a React/Next usage example",
        ),
        step(
            "dashboard_snippet_targets_hosted_asset",
            'src="${options.hostOrigin}/voiceos.js"' in dashboard_helper,
            "the dashboard snippet builder should target /voiceos.js",
        ),
        step(
            "origin_enforcement_test_passed",
            pytest_ok,
            "the focused API test for public widget key + allowed origin should pass",
        ),
        step(
            "hosted_asset_readiness_contract_green",
            bool(readiness.get("steps"))
            and all(
                item.get("ok")
                for item in readiness.get("steps", [])
                if item.get("name")
                not in {"hosted_asset_present", "size_artifact_present"}
            ),
            "all hosted-asset contract checks except the materialized bundle artifacts should be green",
        ),
    ]

    pending = []
    if readiness.get("next_gap"):
        pending.append(str(readiness["next_gap"]))
    if not pytest_ok:
        pending.append("widget_origin_test_failed")

    passed = all(item["ok"] for item in steps)
    report = {
        "scope": "phase5_acceptance_summary",
        "status_date": "2026-08-25",
        "passed": passed,
        "pending": pending,
        "hosted_asset_next_gap": readiness.get("next_gap"),
        "environment_blocker": readiness.get("environment_blocker"),
        "pytest_widget_origin": {
            "passed": pytest_ok,
            "command": "pytest -q tests/test_api.py -k public_widget_session_requires_valid_origin_and_public_key",
            "output": pytest_output if not pytest_ok else "[pytest output omitted on success]",
        },
        "steps": steps,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
