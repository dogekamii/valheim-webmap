"""Installable release archive boundary derived from the runtime web root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = "dist/valheim-webmap-2.7.4.zip"


def test_release_is_an_inspected_installable_archive_not_flat_compiler_output():
    server = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
    packager = (ROOT / "scripts" / "package-release.js").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert 'Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location) ?? string.Empty, "web")' in server
    assert ARCHIVE in packager
    for member in (
        "WebMap/WebMap.dll",
        "WebMap/websocket-sharp.dll",
        "WebMap/THIRD-PARTY-NOTICES.txt",
        "WebMap/web/index.html",
        "WebMap/web/style.css",
        "WebMap/web/mapIcons.png",
        "WebMap/web/tile.webp",
    ):
        assert member in packager
    assert "inspect-release-archive" in workflow
    assert "exactly four files" not in readme
