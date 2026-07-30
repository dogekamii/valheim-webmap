"""Release dependency source provenance, notice, package, and docs contracts."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OPAQUE_WEBSOCKET = ROOT / "libs" / "websocket-sharp.dll"
OPAQUE_SHA256 = "33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244"
UPSTREAM_COMMIT = "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1"
ARCHIVE_URL = f"https://codeload.github.com/sta/websocket-sharp/tar.gz/{UPSTREAM_COMMIT}"
ARCHIVE_SHA256 = "310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a"
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


def test_opaque_repository_dll_is_not_a_canonical_dependency_input():
    assert not OPAQUE_WEBSOCKET.exists()


def test_docker_image_acquires_only_the_exact_hash_locked_source_archive():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for required in (
        ARCHIVE_URL, ARCHIVE_SHA256, "sha256sum --check --strict", "--max-redirs 0",
        "application/x-gzip", "websocket-sharp/websocket-sharp.csproj", "tarfile.open",
        "member.issym()", "member.islnk()", "mono-devel=6.8.0.105+dfsg-3.3+deb12u1",
    ):
        assert required in dockerfile
    assert "github.com/sta/websocket-sharp/archive/refs/heads" not in dockerfile
    assert "github.com/sta/websocket-sharp/archive/refs/tags" not in dockerfile


def test_source_build_precedes_webmap_and_package_proves_artifact_continuity():
    build = (ROOT / "build.cake").read_text(encoding="utf-8")
    project = (ROOT / "WebMap" / "WebMap.csproj").read_text(encoding="utf-8")
    packager = (ROOT / "scripts" / "package-release.js").read_text(encoding="utf-8")
    inspector = (ROOT / "scripts" / "inspect-release-privacy.sh").read_text(encoding="utf-8")
    source_task = build.index('Task("BuildWebsocketSharp")')
    source_command = build.index("xbuild", source_task)
    webmap_build = build.index('dotnet build \\"./WebMap/WebMap.csproj\\"')
    package = build.index("scripts/package-release.js", webmap_build)
    inspect = build.index("scripts/inspect-release-privacy.sh", package)
    assert source_task < source_command < webmap_build < package < inspect
    assert "websocket-sharp-build" in project
    assert "libs\\websocket-sharp.dll" not in project
    assert "sourceBuiltDependency" in packager
    assert "source-built websocket-sharp.dll does not match" in packager
    assert "cmp -s" in inspector
    assert OPAQUE_SHA256 in inspector
    assert "must not match removed opaque repository DLL" in inspector
    assert "1.0.2.29017" in inspector
    assert "5660b08a1845a91e" in inspector


def test_required_notice_records_the_source_build_and_complete_mit_license():
    notice = (ROOT / NOTICE_NAME).read_text(encoding="utf-8")
    for required in (
        "https://github.com/sta/websocket-sharp", UPSTREAM_COMMIT, ARCHIVE_URL,
        ARCHIVE_SHA256, "websocket-sharp/websocket-sharp.csproj", "xbuild", "MIT",
    ):
        assert required in notice
    assert MIT_NOTICE in notice
    assert "unverified" not in notice.lower()
    assert "built from" in notice.lower()


def test_release_packager_accepts_only_the_current_source_built_dependency(tmp_path):
    script = ROOT / "scripts" / "package-release.js"
    output = tmp_path / "package"
    web = tmp_path / "web"
    source = tmp_path / "source-build" / "websocket-sharp.dll"
    output.mkdir()
    web.mkdir()
    source.parent.mkdir()
    source.write_bytes(b"new source-built signed assembly")
    (output / "WebMap.dll").write_bytes(b"compiled plugin")
    shutil.copy2(source, output / "websocket-sharp.dll")
    (output / "WebMap.pdb").write_bytes(b"private symbols")
    (output / "private.cfg").write_text("private", encoding="utf-8")
    (output / "nested").mkdir()
    (output / "nested" / "secret.data").write_text("private", encoding="utf-8")
    (web / "main.0123456789abcdef.js").write_text("console.log('bundle')", encoding="utf-8")

    subprocess.run(
        ["node", str(script), str(output), str(web), str(ROOT / NOTICE_NAME), str(source)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )

    files = sorted(path.name for path in output.iterdir())
    assert files == [NOTICE_NAME, "WebMap.dll", "main.0123456789abcdef.js", "websocket-sharp.dll"]
    assert (output / "websocket-sharp.dll").read_bytes() == source.read_bytes()

    (output / "websocket-sharp.dll").write_bytes(b"fallback prebuilt binary")
    rejected = subprocess.run(
        ["node", str(script), str(output), str(web), str(ROOT / NOTICE_NAME), str(source)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    assert "source-built websocket-sharp.dll does not match" in rejected.stderr


def test_provenance_docs_lock_source_toolchain_command_identity_and_artifact_reporting():
    provenance = (ROOT / "docs" / "DEPENDENCY_PROVENANCE.md").read_text(encoding="utf-8")
    for required in (
        UPSTREAM_COMMIT, ARCHIVE_URL, ARCHIVE_SHA256, "MIT",
        "websocket-sharp/websocket-sharp.csproj", "mono-devel", "xbuild",
        "1.0.2.29017", "5660b08a1845a91e", OPAQUE_SHA256,
        "artifact SHA-256", "not byte-reproducible",
    ):
        assert required.lower() in provenance.lower()
    assert "exact binary-to-source-build provenance remains unverified" not in provenance.lower()


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


def test_changelog_274_records_source_build_without_removed_route_claims():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = changelog.split("## 2.7.4", 1)[1].split("## 2.7.3", 1)[0].lower()
    for required in (
        "aggregate-only", "per-player", "chat", "ping", "pin", "bound", "map digest",
        "cache", "headers", "config", "webhook", "main thread", "teardown", NOTICE_NAME.lower(),
        "source", UPSTREAM_COMMIT,
    ):
        assert required in section
    assert "/messages" not in section
