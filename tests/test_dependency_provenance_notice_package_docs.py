"""Release dependency provenance, notice, packaging, and documentation contracts."""
from pathlib import Path
import hashlib
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WEBSOCKET = ROOT / "libs" / "websocket-sharp.dll"
EXPECTED_SIZE = 254464
EXPECTED_SHA256 = "33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244"
EXPECTED_BLOB = "140cbc4f926d622ec913791d319b7fb99f5d7e58"
NOTICE_NAME = "THIRD-PARTY-NOTICES.txt"
MIT_NOTICE = """The MIT License (MIT)

Copyright (c) 2010-2021 sta.blockhead

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE."""


def test_repository_websocket_binary_is_cryptographically_pinned_and_documented():
    data = WEBSOCKET.read_bytes()
    assert len(data) == EXPECTED_SIZE
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256
    git_blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    assert git_blob == EXPECTED_BLOB

    provenance = (ROOT / "docs" / "DEPENDENCY_PROVENANCE.md").read_text(encoding="utf-8")
    for required in (
        "websocket-sharp.dll", "1.0.2.29017", str(EXPECTED_SIZE), EXPECTED_SHA256,
        EXPECTED_BLOB, "5e5c3361fdac8926f62349bb352cd95c8951f1e9", "2021-04-09",
        "Kyle Paulsen", "https://github.com/sta/websocket-sharp",
        "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1", "MIT",
    ):
        assert required in provenance
    assert re.search(r"exact binary-to-source(?:-commit|-build) provenance[^.]*unverified", provenance, re.I)
    assert "built from 4cbd1e0" not in provenance


def test_required_third_party_notice_contains_the_complete_upstream_notice_and_caveat():
    notice = (ROOT / NOTICE_NAME).read_text(encoding="utf-8")
    assert "https://github.com/sta/websocket-sharp" in notice
    assert "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1" in notice
    assert MIT_NOTICE in notice
    assert re.search(r"exact binary-to-source(?:-commit|-build) provenance[^.]*unverified", notice, re.I)
    assert "built from 4cbd1e0" not in notice


def test_release_packager_emits_only_the_four_allowed_files_and_hashes_the_real_dll(tmp_path):
    script = ROOT / "scripts" / "package-release.js"
    assert script.is_file(), "the canonical release packager is required"
    output = tmp_path / "package"
    web = tmp_path / "web"
    output.mkdir()
    web.mkdir()
    (output / "WebMap.dll").write_bytes(b"compiled plugin")
    shutil.copy2(WEBSOCKET, output / "websocket-sharp.dll")
    (output / "WebMap.pdb").write_bytes(b"private symbols")
    (output / "private.cfg").write_text("private", encoding="utf-8")
    (output / "nested").mkdir()
    (output / "nested" / "secret.data").write_text("private", encoding="utf-8")
    (web / "main.0123456789abcdef.js").write_text("console.log('bundle')", encoding="utf-8")

    subprocess.run(
        ["node", str(script), str(output), str(web), str(ROOT / NOTICE_NAME)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )

    files = sorted(path.name for path in output.iterdir())
    assert files == [NOTICE_NAME, "WebMap.dll", "main.0123456789abcdef.js", "websocket-sharp.dll"]
    assert hashlib.sha256((output / "websocket-sharp.dll").read_bytes()).hexdigest() == EXPECTED_SHA256
    packaged_notice = (output / NOTICE_NAME).read_text(encoding="utf-8")
    assert "Permission is hereby granted" in packaged_notice
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in packaged_notice


def test_release_build_runs_packaging_and_privacy_inspection_with_a_closed_allowlist():
    build = (ROOT / "build.cake").read_text(encoding="utf-8")
    inspector = (ROOT / "scripts" / "inspect-release-privacy.sh").read_text(encoding="utf-8")
    build_start = build.index('DotNetBuild("./WebMap/WebMap.csproj"')
    package_start = build.index("scripts/package-release.js", build_start)
    inspect_start = build.index("scripts/inspect-release-privacy.sh", package_start)
    assert build_start < package_start < inspect_start
    for required in (NOTICE_NAME, EXPECTED_SHA256, "main.[0-9a-f]{16}.js", "exactly four"):
        assert required in inspector
    assert "find \"$output\" -mindepth 1 -maxdepth 1" in inspector
    assert "expected exactly two DLLs" in inspector


def test_readme_describes_the_aggregate_only_public_contract_and_private_optional_features():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (
        "aggregate online count", "process-ephemeral", "JavaScript-safe", "not durable anonymity",
        "terrain", "fog", "intentional map pins", "HTTPS reverse proxy", "aggregate-only privacy model",
        "private quorum activity journal", "private link-claim", "RSVP eligibility",
    ):
        assert required.lower() in readme.lower()
    for forbidden in (
        "live player positions", "in-game pings shown", "connected-player list", "connect/chat messages",
        "exposes player positions", "stable identities", "public chat", "public player names",
    ):
        assert forbidden.lower() not in readme.lower()
    assert "activity and linking do not select an rsvp presence policy" in readme.lower()


def test_changelog_274_records_the_candidate_without_removed_route_claims():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("## 2.7.4", 1)[1].split("## 2.7.3", 1)[0].lower()
    for required in (
        "aggregate-only", "per-player", "chat", "ping", "pin", "bound", "map digest",
        "cache", "headers", "config", "webhook", "main thread", "teardown", NOTICE_NAME.lower(),
    ):
        assert required in section
    assert "/messages" not in section
