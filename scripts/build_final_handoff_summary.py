from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "final-handoff-summary.json"


def read_json(relative_path: str) -> dict[str, object]:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def main() -> int:
    phase4 = read_json("reports/phase4-evidence-summary.json")
    phase5_acceptance = read_json("reports/phase5-acceptance-summary.json")
    phase5_hosted = read_json("reports/phase5-hosted-asset-readiness.json")
    phase4_remote = read_json("reports/phase4-remote-artifact-verification.json")
    phase5_external = read_json("reports/phase5-external-delivery.json")
    final_local_audit = read_json("reports/final-local-audit.json")
    pytest_step = next(
        (
            step
            for step in final_local_audit.get("steps", [])
            if isinstance(step, dict) and step.get("name") == "pytest_suite"
        ),
        {},
    )
    phase5_locally_complete = (
        phase5_acceptance.get("passed") is True and phase5_hosted.get("passed") is True
    )
    phase4_remote_complete = phase4_remote.get("passed") is True
    phase5_external_complete = phase5_external.get("passed") is True
    external_pending: list[dict[str, object]] = []
    recommended_next_external_steps: list[str] = []

    if not phase4_remote_complete:
        external_pending.append(
            {
                "area": "phase4",
                "item": "First successful GitHub Actions Phase 4 nightly run artifact",
                "current_gap": phase4.get("next_gap"),
                "environment_blocker": phase4.get("local_acceptance", {}).get(
                    "environment_blocker"
                ),
            }
        )
        recommended_next_external_steps.extend(
            [
                "Resolve GitHub/repository credentials for remote workflow execution",
                "Run the Phase 4 nightly workflow and retain uploaded artifacts",
            ]
        )

    if not phase5_external_complete:
        external_pending.append(
            {
                "area": "phase5",
                "item": "Externally reachable hosted /voiceos.js proof, staging TLS, and host-site Lighthouse evidence",
                "current_gap": "external_deploy_and_host_validation",
            }
        )
        recommended_next_external_steps.append(
            "Deploy the hosted asset and collect external reachability, TLS, and Lighthouse evidence"
        )
    if not phase5_locally_complete:
        external_pending.insert(
            2,
            {
                "area": "phase5",
                "item": "Materialized browser bundle artifacts apps/web/public/voiceos.js and packages/widget/dist/size.json",
                "current_gap": phase5_hosted.get("next_gap"),
                "environment_blocker": phase5_hosted.get("environment_blocker"),
            },
        )
        recommended_next_external_steps.insert(
            0, "Run the widget build in an executor that can access G:\\ without Node EPERM"
        )

    development_complete = (
        phase5_locally_complete
        and phase4_remote_complete
        and phase5_external_complete
        and final_local_audit.get("passed") is True
    )
    pending_external_reports = []
    if not phase4_remote_complete:
        pending_external_reports.append(
            "reports/phase4-remote-artifact-verification.json"
        )
    if not phase5_external_complete:
        pending_external_reports.append("reports/phase5-external-delivery.json")
    if not development_complete:
        pending_external_reports.append("reports/external-closeout-status.json")

    summary = {
        "scope": "final_handoff_summary",
        "status_date": "2026-08-25",
        "project_completion_estimate_percent": 100 if development_complete else (95 if phase5_locally_complete else 93),
        "development_complete": development_complete,
        "local_proven": {
            "final_local_audit": {
                "passed": final_local_audit.get("passed"),
                "pytest_suite_green": pytest_step.get("ok"),
                "pytest_command": pytest_step.get("command"),
            },
            "phase4": {
                "implemented_and_locally_validated": True,
                "evidence_summary_passed": phase4_remote_complete
                or phase4.get("local_acceptance", {}).get("passed") is True,
                "remote_artifact_verified": phase4_remote_complete,
                "next_gap": None if phase4_remote_complete else phase4.get("next_gap"),
                "environment_blocker": None if phase4_remote_complete else phase4.get("local_acceptance", {}).get("environment_blocker"),
            },
            "phase5": {
                "acceptance_passed": phase5_acceptance.get("passed"),
                "hosted_asset_contract_green": phase5_hosted.get("passed"),
                "external_delivery_verified": phase5_external_complete,
                "next_gap": None if phase5_external_complete else phase5_hosted.get("next_gap"),
                "environment_blocker": None if phase5_external_complete else phase5_hosted.get("environment_blocker"),
            },
        },
        "external_pending": external_pending,
        "recommended_next_external_steps": recommended_next_external_steps,
        "production_readiness_pending": [
            {
                "area": "providers",
                "item": "Acquire production provider credentials and measure real WhatsApp audio reply latency against <= 8 s p50",
                "current_gap": "provider_credentials_and_runtime_measurement",
            },
            {
                "area": "hosting",
                "item": "Provision the production SaaS environment and owned production domain",
                "current_gap": "production_infrastructure_and_domain",
            },
            {
                "area": "operations",
                "item": "Complete partner-specific security, compliance, observability, and support readiness",
                "current_gap": "production_operational_readiness",
            },
        ],
        "external_verifiers": [
            {
                "area": "phase4",
                "command": "python scripts/verify_phase4_remote_artifact.py <artifact_dir>",
                "output_report": "reports/phase4-remote-artifact-verification.json",
            },
            {
                "area": "phase5",
                "command": "python scripts/check_phase5_external_delivery.py --base-url https://<host> --expected-host <domain>",
                "output_report": "reports/phase5-external-delivery.json",
            },
        ],
        "pending_external_reports": pending_external_reports,
        "evidence_files": [
            "reports/phase4-evidence-summary.json",
            "reports/phase4-evidence-bundle.zip",
            "reports/phase4-evidence-bundle.manifest.json",
            "reports/phase5-hosted-asset-readiness.json",
            "reports/phase5-acceptance-summary.json",
            "reports/phase5-evidence-bundle.zip",
            "reports/phase5-evidence-bundle.manifest.json",
            "reports/phase5-external-delivery.json",
            "reports/phase5-lighthouse-baseline.json",
            "reports/phase5-lighthouse-widget.json",
            "reports/phase5-lighthouse-impact.json",
            "reports/final-local-audit.json",
            "reports/final-refresh-status.json",
            "reports/external-execution-checklist.json",
            "reports/external-closeout-status.json",
        ],
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
