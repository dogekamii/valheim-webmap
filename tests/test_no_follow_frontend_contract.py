from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "WebMap" / "web-src" / "map.js").read_text(encoding="utf-8")
INSPECTOR = (ROOT / "scripts" / "inspect-release-privacy.sh").read_text(encoding="utf-8")


def test_browser_map_has_no_player_follow_state_or_api():
    for forbidden in ("followIcon", "setFollowIcon", "centerOnIcon"):
        assert forbidden not in MAP
        assert forbidden in INSPECTOR


def test_browser_icon_collection_and_deferred_updates_are_bounded():
    assert "MAX_MAP_ICONS" in MAP
    add_icon = MAP[MAP.index("const addIcon"):MAP.index("const hideIcon")]
    assert "mapIcons.length" in add_icon and "MAX_MAP_ICONS" in add_icon
    assert "let iconUpdateTimer" in MAP
    assert "clearTimeout(iconUpdateTimer)" in MAP
    assert "iconUpdateTimer = setTimeout" in MAP
    assert "clearTimeout(performUpdateIcons)" not in MAP
