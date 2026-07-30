from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
CONFIG = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
INDEX = (ROOT / "WebMap" / "web-src" / "index.js").read_text(encoding="utf-8")
SOCKET = (ROOT / "WebMap" / "web-src" / "websocket.js").read_text(encoding="utf-8")
INSPECTOR = (ROOT / "scripts" / "inspect-release-privacy.sh").read_text(encoding="utf-8")


def body(source, signature, next_signature):
    start = source.index(signature)
    return source[start:source.index(next_signature, start)]


def test_map_publication_is_cloned_atomic_and_content_addressed():
    assert "sealed class MapPublication" in SERVER
    assert "readonly byte[] Bytes" in SERVER
    assert "readonly string Digest" in SERVER
    publish = body(SERVER, "public void PublishMap", "public void ReplacePins")
    assert "Clone()" in publish
    assert "SHA256.Create()" in publish
    assert "mapPublication = new MapPublication" in publish
    assert "mapSnapshot" not in SERVER


def test_map_route_requires_one_exact_valid_digest_and_fails_closed():
    routes = body(SERVER, "private bool ProcessSpecialRoutes", "public void Reload")
    assert "GetValues(\"v\")" in routes
    assert "values.Length != 1" in routes
    assert "IsValidMapDigest" in routes
    assert "FixedTimeEquals" in routes
    assert "SetImmutable(res)" in routes
    assert '"public, max-age=604800, immutable"' in SERVER
    assert "SetNoStore" in routes
    assert "application/octet-stream" in routes
    assert "ContentLength64" in routes
    assert "map?v=" in INDEX and "encodeURIComponent(config.map_digest)" in INDEX
    assert "URL.createObjectURL" not in INDEX


def test_only_hashed_javascript_is_static_immutable():
    static_files = body(SERVER, "private void ServeStaticFiles", "private void CacheStaticFile")
    assert "IsHashedMainScript" in static_files
    assert 'requestedFile == "index.html"' in static_files
    assert "SetNoStore" in static_files
    assert '"public, max-age=604800, immutable"' in static_files


def test_typed_client_json_is_serializer_backed_and_metadata_minimal():
    client_section = CONFIG[CONFIG.index("ClientConfig"):]
    assert "[Serializable]" in CONFIG
    assert "sealed class ClientConfig" in CONFIG
    assert "JsonUtility.ToJson" in CONFIG
    assert "DictionaryToJson" not in CONFIG
    assert "map_digest" in client_section
    for forbidden in (
        "world_name", "worldSeed", "password", "openServer", "publicServer",
        "DISCORD_WEBHOOK", "URL", "worldDataPath", "mapDataPath",
    ):
        assert forbidden not in client_section


def test_bound_config_is_centrally_validated_and_conservatively_bounded():
    read = body(CONFIG, "public static void ReadConfigFile", "internal static string NormalizeWorldVisibilityMode")
    assert "ValidateSettings();" in read
    validation = body(CONFIG, "private static void ValidateSettings", "internal static string NormalizeWorldVisibilityMode")
    for field in (
        "TEXTURE_SIZE", "PIXEL_SIZE", "EXPLORE_RADIUS", "UPDATE_FOG_TEXTURE_INTERVAL",
        "SAVE_FOG_TEXTURE_INTERVAL", "PLAYER_UPDATE_INTERVAL", "SERVER_PORT",
        "MAX_PINS_PER_USER", "DEFAULT_ZOOM",
    ):
        assert field in validation
    assert "float.IsNaN" in validation and "float.IsInfinity" in validation
    assert "NormalizeWorldVisibilityMode" in validation


def test_reload_is_single_shot_and_socket_state_is_not_amplified():
    assert "let reloading = false" in SOCKET
    assert "if (reloading) return" in SOCKET
    assert "socket = undefined" in SOCKET
    assert "reconnectTimer = undefined" in SOCKET
    assert SOCKET.count("window.location.reload()") == 1
    assert SOCKET.count("new WebSocket") == 1
    assert "console." not in SOCKET


def test_release_inspector_rejects_private_metadata_and_telemetry_protocols():
    for token in (
        "MapMessage", "BroadcastMessage", "BroadcastPing", "/messages", "messages\\n",
        "ping\\n", "max_health", "m_playerName", "m_publicRefPos", "inBed",
        "worldSeed", "password", "openServer", "publicServer", "world_name",
    ):
        assert token in INSPECTOR
    assert "Game/framework TypeRef and MemberRef" in INSPECTOR
    assert "harmless compiler metadata" in INSPECTOR
    assert "map_digest" in INSPECTOR
    assert "online" in INSPECTOR
