import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
CONFIG = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
INDEX = (ROOT / "WebMap" / "web-src" / "index.js").read_text(encoding="utf-8")
SOCKET = (ROOT / "WebMap" / "web-src" / "websocket.js").read_text(encoding="utf-8")
PLAYERS = (ROOT / "WebMap" / "web-src" / "players.js").read_text(encoding="utf-8")
HTML = (ROOT / "WebMap" / "web" / "index.html").read_text(encoding="utf-8")
DRAWDOWN = ROOT / "WebMap" / "web" / "drawdown.js"
BUILD = (ROOT / "build.sh").read_text(encoding="utf-8")
INSPECTOR = ROOT / "scripts" / "inspect-release-privacy.py"


def test_dynamic_and_error_routes_are_no_store_and_security_headers_are_global():
    assert SERVER.count('"no-store"') >= 4
    assert "ApplySecurityHeaders(e.Response)" in SERVER
    assert "SetNoStore" in SERVER
    assert "404" in SERVER and "SetNoStore" in SERVER[SERVER.index("private void ServeStaticFiles"):]
    assert "public, max-age=604800, immutable" in SERVER
    csp = SERVER[SERVER.index("ContentSecurityPolicy"):SERVER.index("private static readonly Dictionary")]
    assert "connect-src 'self'" in csp
    assert "img-src 'self' data:" in csp
    assert "https:" not in csp and "wss:" not in csp


def test_map_is_content_addressed_without_world_metadata_or_blob_urls():
    assert "mapVersion" in SERVER or "mapDigest" in SERVER
    assert 'config["map_version"]' in CONFIG or "map_version" in CONFIG
    assert "SHA256" in SERVER
    assert "req.Url.AbsolutePath" in SERVER
    assert "config.world_name" not in INDEX
    assert "constants.WORLD_NAME" not in INDEX
    assert "world_name" not in CONFIG[CONFIG.index("MakeClientConfigJson"):]
    assert "URL.createObjectURL" not in INDEX
    assert "map_version" in INDEX
    assert "/map?v=" in INDEX or "map?v=" in INDEX
    assert "document.title = 'Valheim WebMap'" in INDEX or 'document.title = "Valheim WebMap"' in INDEX


def test_client_config_has_no_stale_message_limit_and_numeric_inputs_are_bounded_finite():
    assert "MAX_MESSAGES" not in CONFIG
    assert "max_messages" not in CONFIG
    assert "MAX_MESSAGES" not in INDEX
    assert "max_messages" not in INDEX
    assert "ClampSettings" in CONFIG or "ValidateSettings" in CONFIG
    for field in (
        "TEXTURE_SIZE", "PIXEL_SIZE", "EXPLORE_RADIUS", "UPDATE_FOG_TEXTURE_INTERVAL",
        "SAVE_FOG_TEXTURE_INTERVAL", "PLAYER_UPDATE_INTERVAL", "SERVER_PORT",
        "MAX_PINS_PER_USER", "DEFAULT_ZOOM",
    ):
        assert field in CONFIG
    assert "float.IsNaN" in CONFIG and "float.IsInfinity" in CONFIG
    assert "WORLD_VISIBILITY_MODE" in CONFIG
    assert "QUORUM_ACTIVITY_JOURNAL_ENABLED" in CONFIG


def test_public_frontend_has_no_chat_ping_or_per_player_rendering():
    assert 'from "./players"' not in INDEX
    assert "addActionListener('messages'" not in INDEX
    assert "fetch('messages')" not in INDEX
    assert "addActionListener('ping'" not in INDEX
    assert "messageList" not in INDEX
    assert "hideMessageList" not in INDEX
    assert "Hide Messages" not in HTML
    assert 'id="messages"' not in HTML
    for forbidden in (
        "health", "maxHealth", "dead", "pvp", "inbed", "playerMapIcons",
        "followPlayer", "player.id", "player.name", "player.x", "player.z",
    ):
        assert forbidden not in PLAYERS
    assert "online" in PLAYERS


def test_frontend_reload_and_websocket_use_origin_root_with_one_bounded_jittered_reconnect():
    assert "window.location.reload()" in SOCKET
    assert "location.href.split" not in SOCKET
    assert "location.protocol" in SOCKET and "location.host" in SOCKET
    assert "let socket" in SOCKET
    assert "let reconnectTimer" in SOCKET
    assert "clearTimeout(reconnectTimer)" in SOCKET
    assert "Math.random()" in SOCKET
    assert "Math.min" in SOCKET
    assert SOCKET.count("new WebSocket") == 1
    assert "console." not in SOCKET


def test_remote_markdown_images_are_inert_but_safe_links_remain_clickable():
    script = f"""const fs=require('fs'); const vm=require('vm');
vm.runInThisContext(fs.readFileSync({json.dumps(str(DRAWDOWN))}, 'utf8'));
const values = [
 markdown('![x](https://images.invalid/a.png)'),
 markdown('![x](//images.invalid/a.png)'),
 markdown('[safe](https://example.invalid/page)'),
 markdown('[relative](/guide)')
];
process.stdout.write(JSON.stringify(values));"""
    remote, protocol_relative, safe, relative = json.loads(
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout
    )
    assert "<img" not in remote and "<img" not in protocol_relative
    assert '<a href="https://example.invalid/page">safe</a>' in safe
    assert '<a href="/guide">relative</a>' in relative


def test_canonical_release_build_runs_packaged_two_dll_and_js_privacy_inspection():
    assert INSPECTOR.is_file()
    inspector = INSPECTOR.read_text(encoding="utf-8")
    assert "WebMap.dll" in inspector and "websocket-sharp.dll" in inspector
    assert "exactly two DLLs" in inspector
    assert "main.*.js" in inspector
    for forbidden in (
        "MapMessage", "BroadcastMessage", "BroadcastPing", "/messages", "messages\\n",
        "ping\\n", "max_health", "m_playerName", "m_publicRefPos", "inBed",
    ):
        assert forbidden in inspector
    assert "inspect-release-privacy.py" in BUILD
