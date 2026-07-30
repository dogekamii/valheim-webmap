import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")
CONFIG = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
JOURNAL = (ROOT / "WebMap" / "QuorumActivityJournal.cs").read_text(encoding="utf-8")
WEBHOOK_PATH = ROOT / "WebMap" / "DiscordWebHook.cs"
WEBHOOK = WEBHOOK_PATH.read_text(encoding="utf-8") if WEBHOOK_PATH.exists() else ""


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


def test_public_identity_is_process_ephemeral_random_js_safe_and_generic():
    assert "internal static class PublicIdentity" in SERVER
    assert "RandomNumberGenerator.Create()" in SERVER
    assert "9007199254740991" in SERVER
    assert "HashSet<long>" in SERVER
    assert 'Alias = $"Player {aliasNumber}"' in SERVER
    player_response = method_body(SERVER, "private string BuildPlayerSnapshot")
    assert "PublicIdentity.ForPeer(player.m_uid)" in player_response
    assert "player.m_playerName" not in player_response
    for signature in ("public MapMessage(long id", "public void BroadcastPing", "public void BroadcastMessage"):
        body = method_body(SERVER, signature)
        assert "PublicIdentity.ForPeer" in body
        assert "\\n{name}" not in body


def test_pin_authorization_uses_exact_validated_structured_owner():
    assert ".StartsWith(steamid)" not in WEBMAP
    assert "TryGetPinOwner" in WEBMAP or "TryParsePrivatePin" in SERVER
    assert "IsValidOwnerKey" in WEBMAP or "IsValidOwnerKey" in SERVER
    assert "StringComparison.Ordinal" in WEBMAP
    routed = method_body(SERVER if "TryParsePrivatePin" in SERVER else WEBMAP,
                         "private static bool TryParsePrivatePin" if "TryParsePrivatePin" in SERVER else "private static bool IsValidOwnerKey")
    assert "IsNullOrWhiteSpace" in routed
    assert "\\r" in routed and "\\n" in routed and "," in routed
    assert "return false" in routed


def test_future_pin_records_omit_player_names_but_old_rows_remain_readable():
    add_pin = method_body(SERVER, "public void AddPin")
    assert "name" not in re.sub(r"public void AddPin\([^)]*\)", "", add_pin)
    assert "string.Empty" in add_pin or '",,"' in add_pin
    serializer = method_body(SERVER, "private static bool TrySerializePublicPin")
    assert "pinParts.Length" in serializer
    assert "PublicIdentity.ForOwner" in serializer
    assert "pinParts[3]" not in serializer or "identity.Alias" in serializer
    assert "return false" in serializer


def test_pin_commands_use_exact_case_insensitive_tokens_and_prefixes_stay_chat():
    assert "TryParseCommand" in WEBMAP
    parser = method_body(WEBMAP, "private static bool TryParseCommand")
    assert "StringComparison.OrdinalIgnoreCase" in parser
    assert "char.IsWhiteSpace" in parser
    routed = method_body(WEBMAP, "private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)")
    assert '.ToUpper().StartsWith("!PIN")' not in routed
    assert '.ToUpper().StartsWith("!UNDOPIN")' not in routed
    assert '.ToUpper().StartsWith("!DELETEPIN")' not in routed


def test_journal_is_name_free_and_join_leave_do_not_require_display_names():
    assert "m_playerName" not in JOURNAL
    for class_name in ("private class ZNetPatchDisconnect", "private class ZRoutedRpcAddPeerPatch"):
        patch = WEBMAP[WEBMAP.index(class_name):]
        patch = patch[:patch.index("[HarmonyPatch", 1)]
        assert "m_playerName" not in patch
        assert "peer != null" in patch
        assert "peer.m_uid" in patch
    for signature, append, text in (
        ("public void NotifyJoin", "QuorumActivityJournal.AppendJoin(peer)", "A player joined"),
        ("public void NotifyLeave", "QuorumActivityJournal.AppendLeave(peer)", "A player left"),
    ):
        body = method_body(WEBMAP, signature)
        assert text in body
        assert "peer.m_playerName" not in body
        assert body.index(append) < body.index("mapDataServer.AddMessage")
        if "SendDiscordNotification" in body:
            assert body.index(append) < body.index("SendDiscordNotification")


def test_webhook_is_removed_or_https_validated_bounded_async_and_disposable():
    if not WEBHOOK:
        assert "DiscordWebHook" not in WEBMAP
        return
    constructor = method_body(WEBHOOK, "public DiscordWebHook(string url)")
    assert "Uri.TryCreate" in constructor
    assert "Uri.UriSchemeHttps" in constructor
    assert "IsNullOrWhiteSpace" in constructor
    if "new WebClient" in constructor:
        assert constructor.index("Uri.TryCreate") < constructor.index("new WebClient")
    assert "BlockingCollection" in WEBHOOK or "Channel" in WEBHOOK
    assert "boundedCapacity" in WEBHOOK or "Capacity" in WEBHOOK
    assert "CancellationTokenSource" in WEBHOOK
    assert "Task.Run" in WEBHOOK or "new Thread" in WEBHOOK
    assert "UploadValues(" not in method_body(WEBHOOK, "public void SendMessage")
    assert "Timeout" in WEBHOOK
    assert "Dispose" in WEBHOOK


def test_server_metadata_and_webmap_logs_are_minimized():
    set_info = method_body(WEBMAP, "public void SetServerInfo")
    assert set_info.count("serverInfo.Add") == 1
    assert 'serverInfo.Add("serverName"' in set_info
    for secret in ('"password"', '"worldName"', '"worldSeed"', '"openServer"', '"publicServer"'):
        assert secret not in set_info
    owned = SERVER + WEBMAP + WEBHOOK
    for forbidden in (
        "ex.Message", "e.Message", "ex.ToString()", "e.ToString()", "GetServerIP",
        "HandleRoutedRPC:", "WebMap: (say)", "WebMap: (chat)", "WebMap: (ping)",
        "loading existing world: #", "old: #{currentWorldName}", "WORLD_START_POS.ToString()",
    ):
        assert forbidden not in owned
    assert "console." not in "".join(path.read_text(encoding="utf-8") for path in (ROOT / "WebMap" / "web-src").glob("*.js"))
