from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
FRONTEND_CACHE = (ROOT / "WebMap" / "Patches" / "FrontendCacheHeadersPatch.cs").read_text(encoding="utf-8")


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


def test_index_read_boundary_does_not_swallow_response_programming_errors():
    handler = section(FRONTEND_CACHE, "private static bool ServeUncachedIndex", "    }\n}")
    read = handler.index("File.ReadAllBytes")
    assert "catch (IOException)" in handler
    assert "catch (UnauthorizedAccessException)" in handler
    io_failure = handler.index("catch (IOException)", read)
    access_failure = handler.index("catch (UnauthorizedAccessException)", io_failure)
    publish = handler.index("e.Response.ContentType", access_failure)

    # Only the controlled filesystem read is translated to a 404. Response
    # publication failures must reach MapDataServer's sanitized HTTP 500 boundary.
    assert read < io_failure < access_failure < publish
    assert "catch\n            {" not in handler
    assert "exception.Message" not in handler and "ex.Message" not in handler
