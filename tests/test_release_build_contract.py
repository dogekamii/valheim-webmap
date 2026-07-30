"""Static contract for the canonical release build and package path."""
from pathlib import Path
import xml.etree.ElementTree as ET

repo = Path(__file__).parents[1]


def test_canonical_release_runs_browser_dependency_and_webmap_builds_in_order():
    build_cake = (repo / "build.cake").read_text()
    workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
    assert 'var BuildTask = Task("Build")' in build_cake
    assert 'BuildTask.IsDependentOn("BuildWebsocketSharp")' in build_cake
    assert 'BuildTask.IsDependentOn("BuildNpm")' in build_cake
    assert 'Task("BuildWebsocketSharp")' in build_cake
    assert "xbuild" in build_cake
    assert "websocket-sharp/websocket-sharp.csproj" in build_cake
    assert build_cake.index('Task("BuildWebsocketSharp")') < build_cake.index('dotnet build \\"./WebMap/WebMap.csproj\\"')
    assert 'NpmRunScript("build")' in build_cake
    assert "scripts/package-release.js" in build_cake
    assert "scripts/inspect-release-privacy.sh" in build_cake
    assert "Build canonical installable release archive" in workflow
    assert "docker build --build-arg BEPINEX_RELEASE=" in workflow
    assert "webmap-release-build" in workflow
    assert "./build.sh --configuration Release" in workflow


def test_failed_managed_build_steps_emit_sanitized_reusable_annotations():
    build_cake = (repo / "build.cake").read_text()
    diagnostic = (repo / "scripts" / "run-build-step.sh").read_text()
    for step in (
        "websocket source xbuild",
        "WebMap dotnet build",
        "release packager",
        "release privacy inspector",
    ):
        assert step in build_cake
    assert build_cake.count("RunCheckedBuildCommand(") >= 5
    assert '"$@" 2>&1 | tee "$log_file"' in diagnostic
    assert "PIPESTATUS[0]" in diagnostic
    assert "::error title=${step_name} failed::" in diagnostic
    assert "cut -c1-400" in diagnostic
    assert "<path>" in diagnostic


def test_success_artifact_notice_crosses_the_docker_boundary():
    inspector = (repo / "scripts" / "inspect-release-privacy.sh").read_text()
    assert 'if [[ "${GITHUB_ACTIONS:-}" == "true" ]]' not in inspector
    notice = next(line for line in inspector.splitlines() if "::notice file=docs/DEPENDENCY_PROVENANCE.md" in line)
    for required in (
        "$actual_hash", "$artifact_size", "1.0.2.29017", "5660b08a1845a91e",
        "mono-devel=$toolchain",
    ):
        assert required in notice


def test_webmap_compiles_against_only_the_current_source_build_output():
    project = ET.parse(repo / "WebMap" / "WebMap.csproj").getroot()
    references = {
        reference.attrib["Include"]: reference
        for reference in project.findall(".//Reference")
    }
    websocket = references["WebsocketSharp"]
    assert websocket.findtext("HintPath") == r"$(TempDir)websocket-sharp-build\websocket-sharp.dll"
    assert websocket.findtext("Private") == "true"
    assert "libs\\websocket-sharp.dll" not in (repo / "WebMap" / "WebMap.csproj").read_text()


def test_release_contract_inspects_the_installable_archive_not_compiler_staging():
    packager = (repo / "scripts" / "package-release.js").read_text()
    inspector = (repo / "scripts" / "inspect-release-archive.py").read_text()
    privacy = (repo / "scripts" / "inspect-release-privacy.sh").read_text()
    workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
    for required in (
        "dist/valheim-webmap-2.7.4.zip", "WebMap/WebMap.dll",
        "WebMap/websocket-sharp.dll", "WebMap/THIRD-PARTY-NOTICES.txt",
        "WebMap/web/index.html", "WebMap/web/style.css",
        "WebMap/web/mapIcons.png", "WebMap/web/tile.webp",
    ):
        assert required in packager
    for required in (
        "duplicate archive member", "archive member allowlist mismatch",
        "exactly two runtime DLLs", "bundle filename does not match",
        "stylesheet asset graph", "source-built output", "compiler staging output",
    ):
        assert required in inspector
    assert "release archive privacy inspection passed" in privacy
    assert "Inspect canonical release archive" in workflow
    assert "python3 scripts/inspect-release-archive.py" in workflow
    assert "test -s dist/valheim-webmap-2.7.4.zip" in workflow
    assert "Reject compile-only DLLs from compiler staging output" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
