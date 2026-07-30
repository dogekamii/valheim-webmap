from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")
WEBHOOK = (ROOT / "WebMap" / "DiscordWebHook.cs").read_text(encoding="utf-8")
WEB_SOURCES = list((ROOT / "WebMap" / "web-src").glob("*.js"))


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


def test_public_protocol_uses_process_ephemeral_numeric_ids_and_generic_aliases():
    assert "internal static class PublicIdentity" in SERVER
    assert "RandomNumberGenerator.Create()" in SERVER
    assert "Dictionary<string, PublicIdentityView>" in SERVER
    assert "HashSet<long>" in SERVER
    assert 'Alias = $"Player {aliasNumber}"' in SERVER

    player_response = method_body(SERVER, "public string getPlayerResponse")
    assert "PublicIdentity.ForPeer(player.m_uid)" in player_response
    assert '$"{player.m_uid}' not in player_response
    assert "player.m_playerName" not in player_response

    map_message = method_body(SERVER, "public MapMessage(long id")
    assert "PublicIdentity.ForPeer(id)" in map_message
    assert "this.id = id" not in map_message
    assert "this.name = name;" not in map_message

    for signature in ("public void BroadcastPing", "public void BroadcastMessage"):
        body = method_body(SERVER, signature)
        assert "PublicIdentity.ForPeer(id)" in body
        assert "\\n{name}" not in body


def test_public_pin_serialization_transforms_private_ownership_and_fails_closed():
    pins_route = method_body(SERVER, "private bool ProcessSpecialRoutes")
    add_pin = method_body(SERVER, "public void AddPin")
    serializer = method_body(SERVER, "private static bool TrySerializePublicPin")

    assert "SerializePublicPins()" in pins_route
    assert "TrySerializePublicPin" in add_pin
    assert "PublicIdentity.ForOwner" in serializer
    assert "pinParts.Length != 7" in serializer
    assert "return false" in serializer
    assert "Regex.IsMatch" in serializer
    assert "float.TryParse" in serializer
    assert 'string.Join("\\n", pins)' not in pins_route


def test_join_leave_public_messages_are_generic_and_journal_precedes_webhook():
    for signature, journal_call, generic_message in (
        ("public void NotifyJoin", "QuorumActivityJournal.AppendJoin(peer)", "A player joined"),
        ("public void NotifyLeave", "QuorumActivityJournal.AppendLeave(peer)", "A player left"),
    ):
        body = method_body(WEBMAP, signature)
        assert generic_message in body
        assert "peer.m_playerName" not in body
        assert body.index(journal_call) < body.index("SendDiscordNotification")
        assert body.index(journal_call) < body.index("mapDataServer.AddMessage")


def test_disabled_webhook_is_inert_and_enabled_failures_are_isolated():
    constructor = method_body(WEBHOOK, "public DiscordWebHook(string url)")
    send = method_body(WEBHOOK, "public void SendMessage")
    notify_online = method_body(WEBMAP, "public void NotifyOnline")
    notification_helper = method_body(WEBMAP, "private void SendDiscordNotification")

    assert "public bool IsEnabled" in WEBHOOK
    assert constructor.index("IsEnabled") < constructor.index("new WebClient()")
    assert send.index("if (!IsEnabled)") < send.index("new NameValueCollection")
    assert "GetServerIP" not in WEBMAP
    assert 'serverInfo.Add("password"' not in WEBMAP
    assert 'serverInfo["password"]' not in WEBMAP
    assert "SendDiscordNotification" in notify_online
    assert notification_helper.index("if (!discordWebHook.IsEnabled)") < notification_helper.index("createMessage()")
    assert "catch" in notification_helper
    assert 'ZLog.LogWarning("WebMap: Discord webhook notification failed")' in notification_helper
    assert "ex.Message" not in notification_helper
    assert "ex.ToString" not in notification_helper


def test_chat_and_ping_logs_never_include_protocol_content_or_exception_details():
    routed_rpc = method_body(
        WEBMAP,
        "private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)",
    )

    assert 'ZLog.Log($"WebMap: (say)' not in routed_rpc
    assert 'ZLog.Log($"WebMap: (chat)' not in routed_rpc
    assert 'ZLog.Log($"WebMap: (ping)' not in routed_rpc
    assert "ex.ToString" not in routed_rpc
    assert 'ZLog.Log("WebMap: chat message processed")' in routed_rpc
    assert 'ZLog.Log("WebMap: ping processed")' in routed_rpc


def test_frontend_does_not_log_protocol_data_to_the_browser_console():
    offenders = [path.name for path in WEB_SOURCES if "console." in path.read_text(encoding="utf-8")]
    assert offenders == []
