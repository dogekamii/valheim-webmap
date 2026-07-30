"""Static contract for the canonical WebMap release version."""
from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET

# These are the release metadata fields consumed by BepInEx, Thunderstore,
# npm, and the reproducible browser-build lockfile.
EXPECTED_VERSION = "2.7.4"
repo = Path(__file__).parents[1]


def test_release_candidate_version_metadata_is_coherent():
    webmap_source = (repo / "WebMap" / "WebMap.cs").read_text()
    assert re.search(
        rf'public const string VERSION = "{re.escape(EXPECTED_VERSION)}";',
        webmap_source,
    ), "WebMap.VERSION must be the release version"

    project = ET.parse(repo / "WebMap" / "WebMap.csproj").getroot()
    assert project.findtext(".//Version") == EXPECTED_VERSION, "csproj Version must match"

    manifest = json.loads((repo / "manifest.json").read_text())
    assert manifest["version_number"] == EXPECTED_VERSION, (
        "manifest version_number must match"
    )

    package = json.loads((repo / "package.json").read_text())
    assert package["version"] == EXPECTED_VERSION, "package.json version must match"

    package_lock = json.loads((repo / "package-lock.json").read_text())
    assert package_lock["version"] == EXPECTED_VERSION, (
        "package-lock root version must match"
    )
    assert package_lock["packages"][""]["version"] == EXPECTED_VERSION, (
        "package-lock root package version must match"
    )

    readme = (repo / "README.md").read_text()
    assert "2.7.4" in readme, "README must identify the 2.7.4 candidate"
    assert "2.7.3" not in readme, "README current-version claims must be coherent"

    changelog = (repo / "CHANGELOG.md").read_text()
    assert re.search(r"^## 2\.7\.4\b", changelog, re.MULTILINE), (
        "changelog must document the 2.7.4 candidate"
    )
