from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_PATH = REPORTS_DIR / "external-execution-checklist.json"
MARKDOWN_PATH = REPO_ROOT / "EXTERNAL-EXECUTION-CHECKLIST-2026-08-25.md"


def read_json(relative_path: str) -> dict[str, object]:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def render_markdown(checklist: dict[str, object]) -> str:
    artifacts = checklist["artifacts"]
    phase4 = checklist["phase4"]
    phase5 = checklist["phase5"]
    global_section = checklist["global"]
    lines = [
        "# External Execution Checklist - 2026-08-25",
        "",
        "This checklist captures the exact remaining work that must happen outside the current managed executor.",
        "",
        "## Delivery artifacts to identify before external execution",
        "",
        "- Phase 4 evidence bundle:",
        f"  - `{artifacts['phase4_evidence_bundle']['path']}`",
        f"  - SHA-256: `{artifacts['phase4_evidence_bundle']['sha256']}`",
        f"  - bytes: `{artifacts['phase4_evidence_bundle']['bytes']}`",
        "- Phase 5 evidence bundle:",
        f"  - `{artifacts['phase5_evidence_bundle']['path']}`",
        f"  - SHA-256: `{artifacts['phase5_evidence_bundle']['sha256']}`",
        f"  - bytes: `{artifacts['phase5_evidence_bundle']['bytes']}`",
        "- Final handoff bundle manifest:",
        f"  - `{artifacts['final_handoff_bundle_manifest']['path']}`",
        f"  - bundle path: `{artifacts['final_handoff_bundle_manifest']['bundle_path']}`",
        "",
        "## Phase 4",
        "",
        f"Current gap: `{phase4['current_gap']}`",
        "",
        *(
            [
                "Environment blocker:",
                "",
                f"- type: `{phase4['environment_blocker']['type']}`",
                f"- detail: {phase4['environment_blocker']['detail']}",
                f"- current gap mapping: `{phase4['environment_blocker']['current_gap']}`",
                "",
            ]
            if isinstance(phase4.get("environment_blocker"), dict)
            else []
        ),
        "1. Restore GitHub and repository credentials for `mariohidifira/voice_os`",
        "2. Run the Phase 4 nightly workflow in GitHub Actions",
        "3. Retain the uploaded artifacts from the first successful nightly run",
        "4. After provider credentials are available, run the real WhatsApp audio latency measurement and compare it against the `<= 8 s p50` target",
        "",
        "Commands:",
        "",
        *(f"- `{command}`" for command in phase4["commands"]),
        "",
        "## Phase 5",
        "",
        f"Current gap: `{phase5['current_gap']}`",
        "",
        *(
            [
                "Environment blocker:",
                "",
                f"- type: `{phase5['environment_blocker']['type']}`",
                f"- detail: {phase5['environment_blocker']['detail']}",
                *(
                    [f"- missing artifact: `{item}`" for item in phase5["environment_blocker"].get("missing_artifacts", [])]
                    if isinstance(phase5["environment_blocker"].get("missing_artifacts"), list)
                    else []
                ),
                "",
            ]
            if isinstance(phase5.get("environment_blocker"), dict)
            else []
        ),
        *(f"{index}. {item}" for index, item in enumerate(phase5["steps"], start=1)),
        "",
        "Commands:",
        "",
        *(f"- `{command}`" for command in phase5["commands"]),
        "",
        "## External capabilities required",
        "",
        *(f"- {item}" for item in global_section["required_external_capabilities"]),
        "",
        "## Machine-readable companion",
        "",
        "- `reports/external-execution-checklist.json`",
        "",
        "## Verifiers to run during closeout",
        "",
        "- Phase 4 remote artifact:",
        "  - `python scripts/verify_phase4_remote_artifact.py <artifact_dir>`",
        "  - output: `reports/phase4-remote-artifact-verification.json`",
        "- Phase 5 external delivery:",
        "  - `python scripts/check_phase5_external_delivery.py --base-url https://<host> --expected-host <domain>`",
        "  - output: `reports/phase5-external-delivery.json`",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    phase4 = read_json("reports/phase4-evidence-summary.json")
    phase5_hosted = read_json("reports/phase5-hosted-asset-readiness.json")
    phase4_remote = read_json("reports/phase4-remote-artifact-verification.json")
    phase5_external = read_json("reports/phase5-external-delivery.json")
    final_summary = read_json("reports/final-handoff-summary.json")
    phase4_manifest = read_json("reports/phase4-evidence-bundle.manifest.json")
    phase5_manifest = read_json("reports/phase5-evidence-bundle.manifest.json")
    final_manifest = read_json("reports/final-handoff-bundle.manifest.json")
    phase5_local_complete = phase5_hosted.get("passed") is True
    phase4_remote_complete = phase4_remote.get("passed") is True
    phase5_external_complete = phase5_external.get("passed") is True
    phase5_steps = [
        "Deploy the hosted asset and verify `/voiceos.js` is externally reachable",
        "Validate custom-domain TLS in staging",
        "Collect host-site Lighthouse impact evidence",
    ]
    if not phase5_local_complete:
        phase5_steps = [
            "Run the widget build in an environment where Node can access `G:\\` without `EPERM`",
            "Confirm `apps/web/public/voiceos.js` exists",
            "Confirm `packages/widget/dist/size.json` exists",
            *phase5_steps,
        ]
    if phase5_external_complete:
        phase5_steps = []

    checklist = {
        "scope": "external_execution_checklist",
        "status_date": "2026-08-25",
        "artifacts": {
            "phase4_evidence_bundle": {
                "path": phase4_manifest.get("bundle_path"),
                "sha256": phase4_manifest.get("bundle_sha256"),
                "bytes": phase4_manifest.get("bundle_bytes"),
            },
            "phase5_evidence_bundle": {
                "path": phase5_manifest.get("bundle_path"),
                "sha256": phase5_manifest.get("bundle_sha256"),
                "bytes": phase5_manifest.get("bundle_bytes"),
            },
            "final_handoff_bundle_manifest": {
                "path": "reports/final-handoff-bundle.manifest.json",
                "bundle_path": final_manifest.get("bundle_path"),
            },
        },
        "phase4": {
            "current_gap": None if phase4_remote_complete else phase4.get("next_gap"),
            "environment_blocker": None
            if phase4_remote_complete
            else phase4.get("local_acceptance", {}).get("environment_blocker"),
            "commands": [
                "npm --prefix G:\\DEV\\VOICE_OS run phase4:remote:ready",
                "gh workflow run phase4-nightly-whatsapp.yml --repo mariohidifira/voice_os",
                "gh run list --repo mariohidifira/voice_os --workflow phase4-nightly-whatsapp.yml --limit 5",
                "python scripts/verify_phase4_remote_artifact.py <artifact_dir>",
            ],
            "reports": [
                "reports/phase4-remote-readiness.json",
                "reports/phase4-remote-artifact-verification.json",
            ],
            "steps": []
            if phase4_remote_complete
            else [
                "Restore GitHub and repository credentials in an executor that can access mariohidifira/voice_os",
                "Run the Phase 4 nightly workflow in GitHub Actions",
                "Retain the uploaded Phase 4 artifacts from the successful run",
            ],
        },
        "phase5": {
            "current_gap": None
            if phase5_external_complete
            else phase5_hosted.get("next_gap") or "external_deploy_and_host_validation",
            "environment_blocker": None
            if phase5_external_complete
            else phase5_hosted.get("environment_blocker"),
            "commands": [
                "npm --prefix G:\\DEV\\VOICE_OS run phase5:widget:fallback",
                "npm --prefix G:\\DEV\\VOICE_OS run phase5:asset:ready",
                "npm --prefix G:\\DEV\\VOICE_OS run phase5:acceptance",
                "python scripts/check_phase5_external_delivery.py --base-url https://<host>",
                "npm --prefix G:\\DEV\\VOICE_OS run phase5:evidence:package",
                "npm --prefix G:\\DEV\\VOICE_OS run phase5:evidence:verify",
            ],
            "reports": [
                "reports/phase5-hosted-asset-readiness.json",
                "reports/phase5-acceptance-summary.json",
                "reports/phase5-external-delivery.json",
            ],
            "steps": phase5_steps,
        },
        "global": {
            "project_completion_estimate_percent": final_summary.get(
                "project_completion_estimate_percent"
            ),
            "development_complete": phase4_remote_complete and phase5_external_complete,
            "required_external_capabilities": []
            if phase4_remote_complete and phase5_external_complete
            else [
                "GitHub/repository access",
                "Reachable staging deployment surface",
            ]
            + ([] if phase5_local_complete else ["Node-capable environment without G:\\ EPERM"]),
            "production_readiness_capabilities": [
                "Provider credentials and live accounts",
                "Owned production domain and SaaS hosting",
                "Production observability, security, compliance, and support operations",
            ],
        },
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(checklist, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(checklist), encoding="utf-8")
    print(json.dumps(checklist, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
