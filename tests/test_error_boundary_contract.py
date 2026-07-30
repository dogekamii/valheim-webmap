from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")


def section(source, start, end):
    begin = source.index(start)
    return source[begin:source.index(end, begin)]


def test_coroutine_stop_failure_cannot_skip_network_teardown():
    stop = section(SERVER, "public void Stop()", "private void ServeStaticFiles")
    coroutine_stop = stop.index("owner.StopCoroutine(coroutine)")
    websocket_stop = stop.index("webSocketHandler.Sessions", coroutine_stop)
    http_stop = stop.index("httpServer.Stop()", websocket_stop)

    # stopping is published before cleanup and makes later Stop calls no-ops, so
    # the first attempt must contain a coroutine failure before network cleanup.
    coroutine_failure_boundary = stop.index("catch", coroutine_stop)
    assert coroutine_stop < coroutine_failure_boundary < websocket_stop < http_stop
    assert "exception.Message" not in stop and "ex.Message" not in stop
