from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile


REPO_ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH = REPO_ROOT / "reports" / "phase5-evidence-bundle.zip"
MANIFEST_PATH = REPO_ROOT / "reports" / "phase5-evidence-bundle.manifest.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    result: dict[str, object] = {
        "scope": "phase5_evidence_bundle_verification",
        "bundle_exists": ZIP_PATH.is_file(),
        "manifest_exists": MANIFEST_PATH.is_file(),
        "failed_entries": [],
        "missing_entries": [],
    }
    if not ZIP_PATH.is_file() or not MANIFEST_PATH.is_file():
        result["passed"] = False
        print(json.dumps(result, indent=2))
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    bundle_bytes = ZIP_PATH.read_bytes()
    result["bundle_sha256_ok"] = manifest.get("bundle_sha256") == sha256_bytes(bundle_bytes)

    failed_entries: list[dict[str, object]] = []
    missing_entries: list[str] = []
    try:
        with ZipFile(ZIP_PATH, "r") as archive:
            archive_names = set(archive.namelist())
            for item in manifest.get("included", []):
                path = item["path"]
                if path not in archive_names:
                    missing_entries.append(path)
                    continue
                payload = archive.read(path)
                entry_result = {
                    "path": path,
                    "in_zip": True,
                    "bytes_ok": item.get("bytes") == len(payload),
                    "sha256_ok": item.get("sha256") == sha256_bytes(payload),
                }
                if not entry_result["bytes_ok"] or not entry_result["sha256_ok"]:
                    failed_entries.append(entry_result)
    except BadZipFile as exc:
        result["zip_error"] = str(exc)
        result["missing_entries"] = missing_entries
        result["failed_entries"] = failed_entries
        result["passed"] = False
        print(json.dumps(result, indent=2))
        return 1

    result["missing_entries"] = missing_entries
    result["failed_entries"] = failed_entries
    result["passed"] = bool(result["bundle_sha256_ok"]) and not missing_entries and not failed_entries
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
