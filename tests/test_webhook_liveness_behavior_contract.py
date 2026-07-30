from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBHOOK = (ROOT / "WebMap" / "DiscordWebHook.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")


def method_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"unterminated method: {signature}")


def test_invalid_or_disabled_webhook_returns_before_allocating_active_resources():
    constructor = method_body(WEBHOOK, "public DiscordWebHook(string url)")
    assert "string.IsNullOrWhiteSpace(url)" in constructor
    assert "Uri.TryCreate(url, UriKind.Absolute" in constructor
    assert "Uri.UriSchemeHttps" in constructor
    assignment = constructor.index("webHookUri = parsedUri")
    for active_resource in (
        "new BlockingCollection", "new CancellationTokenSource", "new Thread",
    ):
        assert assignment < constructor.index(active_resource)
    for forbidden in (
        "WebRequest.Create", "HttpWebRequest", "Encoding.UTF8", "EscapeDataString",
    ):
        assert forbidden not in constructor
    assert 'ZLog.LogWarning("WebMap: invalid webhook configuration")' in constructor
    assert "LogWarning(url" not in constructor


def test_send_message_is_nonblocking_bounded_and_does_no_network_or_payload_work():
    send = method_body(WEBHOOK, "public void SendMessage")
    assert "TryAdd" in send
    assert "MaxPayloadLength" in send
    for forbidden in (
        "Add(", "WebRequest", "WebClient", "UploadValues", "GetResponse",
        "GetRequestStream", "Encoding.", "EscapeDataString", "new Thread", "Task.Run",
    ):
        assert forbidden not in send
    assert "Server is online" in WEBHOOK
    assert "Server is offline" in WEBHOOK
    assert "A player joined" in WEBHOOK
    assert "A player left" in WEBHOOK


def test_enabled_webhook_has_one_bounded_worker_one_attempt_and_bounded_io():
    assert "BlockingCollection<string>" in WEBHOOK
    assert "boundedCapacity: QueueCapacity" in WEBHOOK
    assert WEBHOOK.count("new Thread") == 1
    assert "IsBackground = true" in WEBHOOK
    assert "CancellationTokenSource" in WEBHOOK
    assert "QueueCapacity" in WEBHOOK
    assert "RequestTimeoutMilliseconds" in WEBHOOK
    assert "ShutdownWaitMilliseconds" in WEBHOOK
    assert "MaxPayloadBytes" in WEBHOOK
    deliver = method_body(WEBHOOK, "private void Deliver")
    assert "WebRequest.Create(webHookUri)" in deliver
    assert "request.Timeout = RequestTimeoutMilliseconds" in deliver
    assert "request.ReadWriteTimeout = RequestTimeoutMilliseconds" in deliver
    assert "cancellation.Token.Register(request.Abort)" in deliver
    assert deliver.count("GetResponse()") == 1
    assert "GetResponseStream" not in deliver
    assert "while" not in deliver
    for forbidden in ("responseBody", "responseText", "ReadToEnd", "Retry", "retry"):
        assert forbidden not in WEBHOOK


def test_webhook_dispose_is_idempotent_cancels_and_bounds_worker_shutdown():
    dispose = method_body(WEBHOOK, "public void Dispose")
    assert "Interlocked.Exchange" in dispose
    assert "CompleteAdding" in dispose
    assert "Cancel()" in dispose
    assert "Join(ShutdownWaitMilliseconds)" in dispose
    assert "queue.Dispose()" in dispose
    assert "cancellation.Dispose()" in dispose
    on_destroy = method_body(WEBMAP, "public void OnDestroy")
    assert "discordWebHook?.Dispose()" in on_destroy
    for forbidden in ("ex.Message", "ex.ToString()", "exception.Message", "exception.ToString()"):
        assert forbidden not in WEBHOOK + on_destroy
