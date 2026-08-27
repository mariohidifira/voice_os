from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_ZIP_DATETIME = (2026, 8, 25, 0, 0, 0)
DEFAULT_FILE_MODE = 0o100644 << 16


def write_deterministic_zip(archive_path: Path, repo_root: Path, members: list[str]) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative_path in sorted(members):
            source = repo_root / relative_path
            payload = source.read_bytes()
            info = ZipInfo(filename=relative_path, date_time=FIXED_ZIP_DATETIME)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = DEFAULT_FILE_MODE
            archive.writestr(info, payload)
