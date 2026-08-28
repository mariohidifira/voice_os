from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "reports" / "phase4-remote-artifact-verification.json"
REQUIRED_ENTRIES = [
    ("reports/phase4-nightly-whatsapp.xml", "file"),
    ("reports/phase4-local-acceptance.json", "file"),
    ("reports/phase4-evidence-summary.json", "file"),
    ("reports/phase4-evidence-bundle.manifest.json", "file"),
    ("reports/phase4-evidence-bundle.zip", "file"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the extracted Phase 4 GitHub Actions artifact contents."
    )
    parser.add_argument(
        "artifact_dir",
        nargs="?",
        default=None,
        help="Directory containing the extracted phase4-nightly-whatsapp artifact",
    )
    return parser.parse_args()


def resolve_artifact_root(candidate: str | None) -> Path:
    if candidate:
        return Path(candidate).expanduser().resolve()
    env_value = os.environ.get("PHASE4_ARTIFACT_DIR") or os.environ.get(
        "PHASE4_REMOTE_ARTIFACT_DIR"
    )
    if env_value:
        return Path(env_value).expanduser().resolve()
    raise SystemExit(
        "Provide <artifact_dir> or set PHASE4_ARTIFACT_DIR / PHASE4_REMOTE_ARTIFACT_DIR."
    )


def find_entry(root: Path, relative_path: str, kind: str) -> Path | None:
    direct = root / relative_path
    if kind == "file" and direct.is_file():
        return direct
    if kind == "dir" and direct.is_dir():
        return direct

    normalized = relative_path.replace("\\", "/")
    for path in root.rglob("*"):
        if kind == "file" and not path.is_file():
            continue
        if kind == "dir" and not path.is_dir():
            continue
        suffix = path.relative_to(root).as_posix()
        if suffix.endswith(normalized):
            return path
    return None


def read_json_if_present(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    artifact_root = resolve_artifact_root(args.artifact_dir)

    checks: list[dict[str, object]] = []
    found_paths: dict[str, Path | None] = {}
    for relative_path, kind in REQUIRED_ENTRIES:
        found = find_entry(artifact_root, relative_path, kind)
        found_paths[relative_path] = found
        checks.append(
            {
                "path": relative_path,
                "kind": kind,
                "ok": found is not None,
                "resolved_path": None if found is None else str(found),
            }
        )

    local_acceptance = read_json_if_present(found_paths["reports/phase4-local-acceptance.json"])
    evidence_summary = read_json_if_present(found_paths["reports/phase4-evidence-summary.json"])

    extra_checks = [
        {
            "name": "local_acceptance_passed",
            "ok": bool(local_acceptance and local_acceptance.get("passed") is True),
            "detail": "phase4-local-acceptance.json should report passed=true inside the remote artifact",
        },
        {
            "name": "evidence_summary_present",
            "ok": evidence_summary is not None,
            "detail": "phase4-evidence-summary.json should be present inside the remote artifact",
        },
    ]

    passed = all(item["ok"] for item in checks) and all(item["ok"] for item in extra_checks)
    report = {
        "scope": "phase4_remote_artifact_verification",
        "status_date": "2026-08-25",
        "artifact_root": str(artifact_root),
        "passed": passed,
        "checks": checks,
        "extra_checks": extra_checks,
        "local_acceptance_passed": None if local_acceptance is None else local_acceptance.get("passed"),
        "evidence_summary_next_gap": None if evidence_summary is None else evidence_summary.get("next_gap"),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
