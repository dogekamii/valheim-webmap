"""Static contract for the canonical release build and package path."""
from pathlib import Path
import xml.etree.ElementTree as ET

repo = Path(__file__).parents[1]
build_cake = (repo / "build.cake").read_text()
workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
packager = (repo / "scripts" / "package-release.js").read_text()
inspector = (repo / "scripts" / "inspect-release-privacy.sh").read_text()
project = ET.parse(repo / "WebMap" / "WebMap.csproj").getroot()

# Browser assets, managed compilation, closed packaging, and privacy inspection
# are one canonical Release task. The workflow executes that task through the
# real Docker + build.sh path rather than reimplementing package assembly.
assert 'var BuildTask = Task("Build")' in build_cake
assert 'BuildTask.IsDependentOn("BuildNpm")' in build_cake
assert 'NpmRunScript("build")' in build_cake
assert "scripts/package-release.js" in build_cake
assert "scripts/inspect-release-privacy.sh" in build_cake
assert "Build release output" in workflow
assert "docker build --build-arg BEPINEX_RELEASE=" in workflow
assert "webmap-release-build" in workflow
assert "./build.sh --configuration Release" in workflow

# websocket-sharp is the only CopyLocal third-party managed dependency.
references = {
    reference.attrib["Include"]: reference
    for reference in project.findall(".//Reference")
}
websocket = references["WebsocketSharp"]
assert websocket.findtext("HintPath") == r"..\libs\websocket-sharp.dll"
assert websocket.findtext("Private") == "true"

# The package allowlist is closed at exactly four regular, non-empty files. It
# deliberately removes PDB/config/private data and any stale or arbitrary file,
# while the inspector separately preserves the exact two-DLL rule.
for required in (
    '"WebMap.dll"', '"websocket-sharp.dll"', '"THIRD-PARTY-NOTICES.txt"',
    r"/^main\.[0-9a-f]{16}\.js$/", "actual.length !== 4", "fs.rmSync",
):
    assert required in packager
assert "expected exactly four release files" in inspector
assert "expected exactly two DLLs" in inspector
assert "sha256sum" in inspector
assert "release privacy inspection passed" in inspector
assert "test -s WebMap/bin/Release/net48/WebMap.dll" in workflow
assert "test -s WebMap/bin/Release/net48/websocket-sharp.dll" in workflow
assert "test ! -e WebMap/web/main.js" in workflow
