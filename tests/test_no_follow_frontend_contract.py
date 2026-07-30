from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = (ROOT / "WebMap" / "web-src" / "map.js").read_text(encoding="utf-8")
INSPECTOR = (ROOT / "scripts" / "inspect-release-privacy.sh").read_text(encoding="utf-8")


def test_browser_map_has_no_player_follow_state_or_api():
    for forbidden in ("followIcon", "setFollowIcon", "centerOnIcon"):
        assert forbidden not in MAP
        assert forbidden in INSPECTOR
