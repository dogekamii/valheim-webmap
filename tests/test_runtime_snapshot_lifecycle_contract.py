from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")


def section(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


def test_unity_state_is_published_only_by_a_main_thread_coroutine():
    assert "System.Threading.Timer" not in SERVER
    assert "PublishSnapshotsOnMainThread" in SERVER
    assert "IEnumerator" in SERVER and "WaitForSeconds" in SERVER
    publisher = section(SERVER, "PublishSnapshotsOnMainThread", "public static MapDataServer")
    assert "players.Count" in publisher
    assert "EncodeTextureToPng" in publisher
    assert "ZDOMan" not in publisher
    assert "m_uid" not in publisher
    assert "m_playerName" not in publisher


def test_workers_read_only_immutable_aggregate_fog_and_pin_snapshots():
    assert "volatile string playerSnapshot" in SERVER
    assert "volatile byte[] pinSnapshot" in SERVER
    assert "volatile byte[] fogSnapshot" in SERVER
    assert "messageSnapshot" not in SERVER
    routes = section(SERVER, "private bool ProcessSpecialRoutes", "public void Reload")
    assert "EncodeTextureToPng" not in routes
    assert 'string.Join("\\n", pins)' not in routes
    websocket = section(SERVER, "public class WebSocketHandler", "public class MapDataServer")
    assert "ZDOMan" not in websocket
    assert "GetPlayerSnapshot" in websocket
    assert ".Broadcast(playerSnapshot" not in SERVER


def test_cached_players_protocol_is_only_a_bounded_aggregate_count():
    snapshot = section(SERVER, "BuildPlayerSnapshot", "PublishSnapshotsOnMainThread")
    assert '"online"' in snapshot
    assert "Math.Min" in snapshot and "Math.Max" in snapshot
    for forbidden in (
        "m_uid", "m_playerName", "m_characterID", "GetPosition", "max_health",
        'GetFloat("health"', 'GetBool("dead"', 'GetBool("pvp"', 'GetBool("inBed"',
        "PublicIdentity.ForPeer", "Alias", "Vector3",
    ):
        assert forbidden not in snapshot


def test_file_cache_is_synchronized_and_shutdown_is_idempotent():
    assert "fileCacheSync" in SERVER
    static_section = section(SERVER, "private void ServeStaticFiles", "private bool ProcessSpecialRoutes")
    serve_body = static_section[:static_section.index("private void CacheStaticFile")]
    assert "lock (fileCacheSync)" in serve_body
    assert "lock (fileCacheSync)" not in serve_body[serve_body.index("File.ReadAllBytes"):]
    stop = section(SERVER, "public void Stop", "private void ServeStaticFiles")
    assert "stopping" in stop
    assert "StopCoroutine" in stop
    assert "httpServer.Stop()" in stop
    assert "webSocketHandler.Sessions.CloseSession" in stop
    assert "__instance" in stop
    on_destroy = section(WEBMAP, "public void OnDestroy", "public void Online")
    assert "mapDataServer?.Stop()" in on_destroy
    assert "discordWebHook?.Dispose()" in on_destroy


def test_websocket_input_is_small_text_exact_single_request_without_amplification():
    websocket = section(SERVER, "public class WebSocketHandler", "public class MapDataServer")
    assert "e.IsText" in websocket
    assert "e.RawData" in websocket
    assert "32" in websocket
    assert "playersSent" in websocket
    assert "StringComparison.Ordinal" in websocket
    assert "GetPlayerSnapshot" in websocket
    assert "Close(" in websocket
    assert "e.Data.ToString()" not in websocket
    assert "ZLog" not in websocket
