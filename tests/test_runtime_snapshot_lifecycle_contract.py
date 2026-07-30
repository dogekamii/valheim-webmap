from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")


def section(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


def test_unity_state_is_snapshotted_only_on_the_main_thread():
    assert "System.Threading.Timer" not in SERVER
    assert "PublishSnapshotsOnMainThread" in SERVER
    assert "IEnumerator" in SERVER and "WaitForSeconds" in SERVER
    assert "ZDOMan.instance" in section(SERVER, "PublishSnapshotsOnMainThread", "public static MapDataServer")
    assert "EncodeTextureToPng" in section(SERVER, "PublishSnapshotsOnMainThread", "public static MapDataServer")


def test_http_and_websocket_threads_only_read_immutable_snapshots():
    assert "volatile byte[] playerSnapshot" in SERVER
    assert "volatile byte[] messageSnapshot" in SERVER
    assert "volatile byte[] pinSnapshot" in SERVER
    assert "volatile byte[] fogSnapshot" in SERVER
    routes = section(SERVER, "private bool ProcessSpecialRoutes", "public void Reload")
    assert "EncodeTextureToPng" not in routes
    assert "sentMessages.ForEach" not in routes
    assert 'string.Join("\\n", pins)' not in routes
    websocket = section(SERVER, "public class WebSocketHandler", "public class MapDataServer")
    assert "ZDOMan" not in websocket
    assert "getPlayerResponse" not in websocket
    assert "GetPlayerSnapshot" in websocket


def test_file_cache_is_synchronized_and_shutdown_is_idempotent():
    assert "fileCacheSync" in SERVER
    static_files = section(SERVER, "private void ServeStaticFiles", "private bool ProcessSpecialRoutes")
    assert "lock (fileCacheSync)" in static_files
    stop = section(SERVER, "public void Stop", "private void ServeStaticFiles")
    assert "stopping" in stop
    assert "httpServer.Stop()" in stop
    assert "webSocketHandler.Sessions.CloseSession" in stop or "webSocketHandler.Sessions.CloseAll" in stop
    on_destroy = section(WEBMAP, "public void OnDestroy", "public void Online")
    assert "mapDataServer?.Stop()" in on_destroy
    assert "discordWebHook?.Dispose()" in on_destroy


def test_websocket_input_is_small_text_single_request_without_amplification():
    websocket = section(SERVER, "public class WebSocketHandler", "public class MapDataServer")
    assert "e.IsText" in websocket
    assert "RawData" in websocket
    assert "32" in websocket
    assert "playersSent" in websocket
    assert "StringComparison.Ordinal" in websocket
    assert "Close(" in websocket
    assert "e.Data.ToString()" not in websocket
