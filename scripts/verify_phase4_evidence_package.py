"""Verify the Phase 4 evidence bundle against its manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
PACKAGE_PATH = REPORTS_DIR / "phase4-evidence-bundle.zip"
MANIFEST_PATH = REPORTS_DIR / "phase4-evidence-bundle.manifest.json"
TODAY = "2026-08-25"


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    bundle_ok = PACKAGE_PATH.exists()
    included_results: list[dict[str, Any]] = []

    if not bundle_ok:
        raise FileNotFoundError(f"Missing bundle: {PACKAGE_PATH}")

    bundle_sha256 = _sha256_file(PACKAGE_PATH)
    try:
        with ZipFile(PACKAGE_PATH) as zf:
            names = set(zf.namelist())
            for item in list(manifest.get("included") or []):
                rel = str(item["path"])
                result = {
                    "path": rel,
                    "manifest_bytes": item.get("bytes"),
                    "manifest_sha256": item.get("sha256"),
                    "in_zip": rel in names,
                    "bytes_ok": False,
                    "sha256_ok": False,
                }
                if rel in names:
                    data = zf.read(rel)
                    result["zip_bytes"] = len(data)
                    result["zip_sha256"] = _sha256_bytes(data)
                    result["bytes_ok"] = len(data) == item.get("bytes")
                    result["sha256_ok"] = result["zip_sha256"] == item.get("sha256")
                included_results.append(result)
    except BadZipFile as exc:
        summary = {
            "date": TODAY,
            "scope": "phase4_evidence_bundle_verification",
            "bundle_path": manifest.get("bundle_path"),
            "bundle_exists": bundle_ok,
            "bundle_sha256_ok": False,
            "missing_entries": [],
            "failed_entries": [],
            "entries": [],
            "zip_error": str(exc),
            "passed": False,
        }
        print(json.dumps(summary, indent=2))
        return 1

    summary = {
        "date": TODAY,
        "scope": "phase4_evidence_bundle_verification",
        "bundle_path": manifest.get("bundle_path"),
        "bundle_exists": bundle_ok,
        "bundle_sha256_ok": bundle_sha256 == manifest.get("bundle_sha256"),
        "missing_entries": [r["path"] for r in included_results if not r["in_zip"]],
        "failed_entries": [
            r["path"]
            for r in included_results
            if not (r["in_zip"] and r["bytes_ok"] and r["sha256_ok"])
        ],
        "entries": included_results,
        "passed": bundle_ok
        and bundle_sha256 == manifest.get("bundle_sha256")
        and all(r["in_zip"] and r["bytes_ok"] and r["sha256_ok"] for r in included_results),
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
