from __future__ import annotations

import json
from pathlib import Path

from scripts import materialize_pending_external_reports as pending_reports
from scripts.refresh_final_handoff import _summarize_parsed


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_materialize_pending_external_reports_creates_explicit_placeholders(
    tmp_path: Path, monkeypatch: object
) -> None:
    write_json(
        tmp_path / "reports" / "phase4-evidence-summary.json",
        {
            "next_gap": "remote_repo_access",
            "local_acceptance": {
                "environment_blocker": {"type": "node_g_drive_eperm"}
            },
        },
    )
    write_json(
        tmp_path / "reports" / "phase5-hosted-asset-readiness.json",
        {
            "next_gap": "widget_bundle_not_built_in_executor",
            "environment_blocker": {"type": "widget_bundle_not_built_in_executor"},
        },
    )
    monkeypatch.setattr(pending_reports, "REPO_ROOT", tmp_path)

    assert pending_reports.main() == 0

    phase4 = json.loads(
        (tmp_path / "reports" / "phase4-remote-artifact-verification.json").read_text()
    )
    phase5 = json.loads(
        (tmp_path / "reports" / "phase5-external-delivery.json").read_text()
    )
    assert phase4["pending"] is True
    assert phase4["passed"] is False
    assert phase4["local_reference"]["phase4_next_gap"] == "remote_repo_access"
    assert phase5["pending"] is True
    assert phase5["passed"] is False
    assert (
        phase5["local_reference"]["phase5_next_gap"]
        == "widget_bundle_not_built_in_executor"
    )


def test_materialize_pending_external_reports_preserves_existing_evidence(
    tmp_path: Path, monkeypatch: object
) -> None:
    phase4_path = tmp_path / "reports" / "phase4-remote-artifact-verification.json"
    phase5_path = tmp_path / "reports" / "phase5-external-delivery.json"
    write_json(phase4_path, {"scope": "phase4_remote_artifact_verification", "passed": True})
    write_json(phase5_path, {"scope": "phase5_external_delivery", "passed": True})
    phase4_before = phase4_path.read_bytes()
    phase5_before = phase5_path.read_bytes()
    monkeypatch.setattr(pending_reports, "REPO_ROOT", tmp_path)

    assert pending_reports.main() == 0

    assert phase4_path.read_bytes() == phase4_before
    assert phase5_path.read_bytes() == phase5_before


def test_materialize_pending_external_reports_refreshes_stale_placeholder(
    tmp_path: Path, monkeypatch: object
) -> None:
    phase5_path = tmp_path / "reports" / "phase5-external-delivery.json"
    write_json(
        phase5_path,
        {
            "scope": "phase5_external_delivery",
            "passed": False,
            "pending": True,
            "local_reference": {"phase5_next_gap": "stale_gap"},
        },
    )
    write_json(
        tmp_path / "reports" / "phase5-hosted-asset-readiness.json",
        {"passed": True, "next_gap": None, "environment_blocker": None},
    )
    monkeypatch.setattr(pending_reports, "REPO_ROOT", tmp_path)

    assert pending_reports.main() == 0

    refreshed = json.loads(phase5_path.read_text(encoding="utf-8"))
    assert refreshed["pending"] is True
    assert refreshed["local_reference"]["phase5_next_gap"] is None
    assert refreshed["local_reference"]["environment_blocker"] is None


def test_refresh_summary_preserves_counts_when_input_is_already_summarized() -> None:
    parsed = {
        "scope": "final_handoff_summary",
        "external_pending_count": 4,
        "evidence_files_count": 11,
    }

    summary = _summarize_parsed("final_handoff_summary", parsed)

    assert summary["external_pending_count"] == 4
    assert summary["evidence_files_count"] == 11


def test_refresh_summary_preserves_package_count_when_already_summarized() -> None:
    parsed = {
        "scope": "phase4_evidence_bundle",
        "bundle_path": "reports/phase4-evidence-bundle.zip",
        "included_count": 7,
    }

    summary = _summarize_parsed("phase4_evidence_package", parsed)

    assert summary["included_count"] == 7


def test_refresh_summary_accepts_full_and_summarized_external_checklist() -> None:
    full = {
        "scope": "external_execution_checklist",
        "phase4": {"current_gap": "remote_repo_access"},
        "phase5": {"current_gap": "widget_bundle_not_built_in_executor"},
        "global": {"project_completion_estimate_percent": 93},
    }
    summarized = {
        "scope": "external_execution_checklist",
        "phase4_current_gap": "remote_repo_access",
        "phase5_current_gap": "widget_bundle_not_built_in_executor",
        "project_completion_estimate_percent": 93,
    }

    full_summary = _summarize_parsed("final_external_checklist", full)
    summarized_summary = _summarize_parsed("final_external_checklist", summarized)

    assert full_summary["phase4_current_gap"] == summarized_summary["phase4_current_gap"]
    assert full_summary["phase5_current_gap"] == summarized_summary["phase5_current_gap"]
    assert (
        full_summary["project_completion_estimate_percent"]
        == summarized_summary["project_completion_estimate_percent"]
        == 93
    )
