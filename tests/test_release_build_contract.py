"""Static contract for the reproducible release build path.

The project has no checked-in zip packaging script.  This test therefore
verifies the actual Cake build path and the CI job that executes it, rather
than incorrectly inferring release-archive contents from one MSBuild setting.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

repo = Path(__file__).parents[1]
build_cake = (repo / "build.cake").read_text()
workflow = (repo / ".github" / "workflows" / "tests.yml").read_text()
project = ET.parse(repo / "WebMap" / "WebMap.csproj").getroot()

# The release target must build the browser assets as part of the same Cake
# dependency graph as the .NET plugin build.
assert 'var BuildTask = Task("Build")' in build_cake
assert 'BuildTask.IsDependentOn("BuildNpm")' in build_cake
assert 'NpmRunScript("build")' in build_cake

# websocket-sharp is a runtime dependency.  CopyLocal is necessary, but it is
# not by itself evidence about a release archive; CI below checks build output.
references = {
    reference.attrib["Include"]: reference
    for reference in project.findall(".//Reference")
}
websocket = references["WebsocketSharp"]
assert websocket.findtext("HintPath") == r"..\libs\websocket-sharp.dll"
assert websocket.findtext("Private") == "true"

# Exercise the repository's real Docker + build.sh + build.cake mechanics on
# CI, then verify the release output directory contains the plugin, its managed
# runtime dependency, and the browser bundle produced by BuildNpm.
assert "Build release output" in workflow
assert "docker build --build-arg BEPINEX_RELEASE=" in workflow
assert "webmap-release-build" in workflow
assert "./build.sh --configuration Release" in workflow
assert "test -s WebMap/bin/Release/net48/WebMap.dll" in workflow
assert "test -s WebMap/bin/Release/net48/websocket-sharp.dll" in workflow
assert "test -s WebMap/web/main.js" in workflow
