#!/usr/bin/env python3
"""Create the deterministic closed-allowlist WebMap release ZIP."""
from pathlib import Path, PurePosixPath
import os
import stat
import sys
import zipfile


def fail(message: str) -> None:
    raise SystemExit(f"release archive creation failed: {message}")


if len(sys.argv) < 5:
    fail("expected staging root, archive path, and explicit members")

staging = Path(sys.argv[1]).resolve()
archive_path = Path(sys.argv[2]).resolve()
expected = tuple(sorted(sys.argv[3:]))
if len(expected) != len(set(expected)):
    fail("duplicate allowlist member")
if not staging.is_dir():
    fail("staging root is missing")

actual = []
for root, directories, files in os.walk(staging, followlinks=False):
    root_path = Path(root)
    for directory in directories:
        if (root_path / directory).is_symlink():
            fail("staging contains a symbolic link")
    for name in files:
        source = root_path / name
        relative = source.relative_to(staging).as_posix()
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] != "WebMap":
            fail("unsafe staging path")
        mode = source.lstat().st_mode
        if not stat.S_ISREG(mode) or source.stat().st_size == 0:
            fail(f"member is not a non-empty regular file: {relative}")
        actual.append(relative)
if tuple(sorted(actual)) != expected:
    fail("staging does not match the closed member allowlist")

archive_path.parent.mkdir(parents=True, exist_ok=True)
temporary = archive_path.with_suffix(archive_path.suffix + ".tmp")
temporary.unlink(missing_ok=True)
try:
    with zipfile.ZipFile(temporary, "w") as archive:
        for member in expected:
            source = staging / Path(*PurePosixPath(member).parts)
            info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(temporary, archive_path)
finally:
    temporary.unlink(missing_ok=True)
