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
    assert build_cake.index('Task("BuildWebsocketSharp")') < build_cake.index('DotNetBuild("./WebMap/WebMap.csproj"')
    assert 'NpmRunScript("build")' in build_cake
    assert "scripts/package-release.js" in build_cake
    assert "scripts/inspect-release-privacy.sh" in build_cake
    assert "Build release output" in workflow
    assert "docker build --build-arg BEPINEX_RELEASE=" in workflow
    assert "webmap-release-build" in workflow
    assert "./build.sh --configuration Release" in workflow


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


def test_package_contract_remains_exactly_four_files_and_two_dlls():
    packager = (repo / "scripts" / "package-release.js").read_text()
    inspector = (repo / "scripts" / "inspect-release-privacy.sh").read_text()
    for required in (
        '"WebMap.dll"', '"websocket-sharp.dll"', '"THIRD-PARTY-NOTICES.txt"',
        r"/^main\.[0-9a-f]{16}\.js$/", "actual.length !== 4", "fs.rmSync",
    ):
        assert required in packager
    assert "expected exactly four release files" in inspector
    assert "expected exactly two DLLs" in inspector
    assert "sha256sum" in inspector
    assert "release privacy inspection passed" in inspector
    workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
    assert "test -s WebMap/bin/Release/net48/WebMap.dll" in workflow
    assert "test -s WebMap/bin/Release/net48/websocket-sharp.dll" in workflow
    assert "test ! -e WebMap/web/main.js" in workflow
