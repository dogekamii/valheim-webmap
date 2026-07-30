#!/usr/bin/env python3
"""Synchronize the reviewed 2.7.4 source candidate metadata without tagging."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "2.7.3"
NEW = "2.7.4"


def replace(path, old, new, expected_count=1):
    target = ROOT / path
    text = target.read_text(encoding="utf-8-sig")
    count = text.count(old)
    if count != expected_count:
        raise SystemExit(f"{path}: expected {expected_count} occurrences, found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace("WebMap/WebMap.cs", 'public const string VERSION = "2.7.3";', 'public const string VERSION = "2.7.4";')
replace("WebMap/WebMap.csproj", "<Version>2.7.3</Version>", "<Version>2.7.4</Version>")
replace("manifest.json", '"version_number": "2.7.3"', '"version_number": "2.7.4"')
replace("package.json", '"version": "2.7.3"', '"version": "2.7.4"')
replace("package-lock.json", '"version": "2.7.3"', '"version": "2.7.4"', expected_count=2)
replace("README.md", OLD, NEW, expected_count=3)

changelog_path = ROOT / "CHANGELOG.md"
changelog = changelog_path.read_text(encoding="utf-8")
marker = "## 2.7.4 — 2026-07-30"
if marker in changelog:
    raise SystemExit("CHANGELOG.md already contains the 2.7.4 entry")
entry = """## 2.7.4 — 2026-07-30

### Security

- Restrict chat-rendered image sources to same-origin relative paths while preserving safe clickable links.
- Apply MIME sniffing, referrer, frame, and same-origin Content Security Policy headers to every HTTP response path.
- Set quorum journals to `0640` after opening and before writing, preserving fail-closed writes while granting the designated AMP group read access.
- Pin GitHub Actions to reviewed commits, use read-only workflow permissions, and avoid duplicate feature-branch push runs.

### Fixed

- Minimize new quorum join/leave records, remove visitor endpoint logging, correct the `/messages` media type, and bind the test setting independently from debug.
- Keep only `WebMap.dll` and `websocket-sharp.dll` in the release payload and refresh audited npm dependencies.

"""
changelog = changelog.replace("## Unreleased\n\n", "## Unreleased\n\n" + entry, 1)
changelog_path.write_text(changelog, encoding="utf-8")
