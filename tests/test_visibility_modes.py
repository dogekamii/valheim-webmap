from pathlib import Path

repo = Path(__file__).parents[1]
config_source = (repo / "WebMap" / "Config.cs").read_text()
client_source = (repo / "WebMap" / "web-src" / "index.js").read_text()
map_source = (repo / "WebMap" / "web-src" / "map.js").read_text()
project_source = (repo / "WebMap" / "WebMap.csproj").read_text()
readme = (repo / "README.md").read_text()
changelog = (repo / "CHANGELOG.md").read_text()

# The server owner selects the policy. Legacy and invalid configuration must
# remain fully fogged, and only the three documented policies are accepted.
assert 'WORLD_VISIBILITY_MODE = "fogged"' in config_source
assert 'world_visibility_mode' in config_source
assert '"fogged", "hybrid", "full"' in config_source
assert 'NormalizeWorldVisibilityMode' in config_source
assert 'world_visibility_mode = WORLD_VISIBILITY_MODE' in config_source

# Browser rendering must consume the server-provided policy and defensively
# retain fogged rendering when a response is missing or malformed.
assert 'normalizeWorldVisibilityMode(config.world_visibility_mode)' in client_source
assert 'visibilityMode' in map_source
assert "visibilityMode !== 'full'" in map_source
assert "visibilityMode === 'hybrid'" in map_source
assert 'HYBRID_MAP_OPACITY' in map_source

# CopyLocal remains a project-level contract; the release-build test verifies output.
assert '<Private>true</Private>' in project_source

# Operators need a discoverable, owner-controlled configuration contract.
assert 'world_visibility_mode' in readme
assert 'world_visibility_mode' in changelog
