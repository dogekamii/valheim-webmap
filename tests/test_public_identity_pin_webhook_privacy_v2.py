import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
WEBMAP = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")
CONFIG = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
JOURNAL = (ROOT / "WebMap" / "QuorumActivityJournal.cs").read_text(encoding="utf-8")
LINK = (ROOT / "WebMap" / "QuorumLinkClaimPatch.cs").read_text(encoding="utf-8")
WEBHOOK_PATH = ROOT / "WebMap" / "DiscordWebHook.cs"
WEBHOOK = WEBHOOK_PATH.read_text(encoding="utf-8") if WEBHOOK_PATH.exists() else ""


def method_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{": depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0: return source[brace + 1:index]
    raise AssertionError(f"unterminated method: {signature}")


def test_public_identity_is_process_ephemeral_js_safe_and_used_only_for_pin_owners():
    assert "internal static class PublicIdentity" in SERVER
    assert "RandomNumberGenerator.Create()" in SERVER
    assert "9007199254740991" in SERVER
    assert "HashSet<long>" in SERVER
    assert '$"Player {aliasNumber}"' in SERVER
    serializer = method_body(SERVER, "private static bool TrySerializePublicPin")
    assert "PublicIdentity.TryForOwner" in serializer
    player_snapshot = method_body(SERVER, "private string BuildPlayerSnapshot")
    assert "PublicIdentity" not in player_snapshot and "Alias" not in player_snapshot
    assert "m_uid" not in player_snapshot and "m_playerName" not in player_snapshot


def test_no_public_chat_message_or_ping_protocol_exists():
    combined = SERVER + WEBMAP
    for forbidden in ("struct MapMessage", "BroadcastMessage", "BroadcastPing", "AddMessage(", 'case "/messages"', 'Broadcast("message', 'Broadcast("messages', 'Broadcast("ping', "sentMessages", "newMessages"):
        assert forbidden not in combined


def test_pin_authorization_uses_exact_validated_structured_owner():
    assert ".StartsWith(steamid)" not in WEBMAP
    assert "TryGetPinOwner" in SERVER and "IsValidOwnerKey" in SERVER
    assert "StringComparison.Ordinal" in WEBMAP
    routed = method_body(SERVER, "private static bool TryParsePrivatePin")
    assert "IsNullOrWhiteSpace" in routed and "\\r" in routed and "\\n" in routed and "," in routed
    assert "return false" in routed


def test_private_pin_parser_rejects_noncanonical_malformed_and_oversized_records():
    parser = method_body(SERVER, "private static bool TryParsePrivatePin")
    assert "parts.Length != 7" in parser and "MaxPrivatePinRecordLength" in parser
    assert "IsValidOwnerKey(parts[0])" in parser
    assert "IsSafePinToken(parts[1], MaxPinIdLength)" in parser
    assert "IsSafePinToken(parts[2], MaxPinTypeLength)" in parser
    assert "IsSafeLegacyName(parts[3])" in parser
    assert "TryParseCoordinate(parts[4]" in parser and "TryParseCoordinate(parts[5]" in parser
    assert "IsSafePublicPinText(parts[6])" in parser
    assert "float.IsNaN" in SERVER and "float.IsInfinity" in SERVER
    assert "CultureInfo.InvariantCulture" in SERVER and "MaxPinCoordinate" in SERVER
    for bound in ("MaxOwnerKeyLength", "MaxPinIdLength", "MaxPinTypeLength", "MaxLegacyNameLength", "MaxPublicPinTextLength"):
        assert bound in SERVER
    assert "char.IsControl" in SERVER


def test_only_validated_private_pins_can_enter_storage_or_live_broadcasts():
    replace = method_body(SERVER, "public void ReplacePins")
    assert replace.index("TryParsePrivatePin") < replace.index("privatePins.Add")
    add = method_body(SERVER, "public void AddPin")
    assert add.index("TryParsePrivatePin(record") < add.index("privatePins.Add")
    publish = method_body(SERVER, "private void PublishPinSnapshot")
    assert "TrySerializePublicPin" in publish and "serialized.Add" in publish


def test_future_pin_records_omit_player_names_but_old_rows_remain_readable():
    add_pin = method_body(SERVER, "public void AddPin")
    assert "name" not in re.sub(r"public void AddPin\([^)]*\)", "", add_pin)
    assert "string.Empty" in add_pin or '",,"' in add_pin
    serializer = method_body(SERVER, "private static bool TrySerializePublicPin")
    assert "pinParts.Length" in serializer and "PublicIdentity.TryForOwner" in serializer
    assert "pinParts[3]" not in serializer or "identity.Alias" in serializer
    assert "return false" in serializer


def test_pin_commands_use_exact_case_insensitive_tokens_and_prefixes_stay_chat():
    parser = method_body(WEBMAP, "private static bool TryParseCommand")
    assert "StringComparison.OrdinalIgnoreCase" in parser and "char.IsWhiteSpace" in parser
    routed = method_body(WEBMAP, "private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)")
    assert '.ToUpper().StartsWith("!PIN")' not in routed
    assert '.ToUpper().StartsWith("!UNDOPIN")' not in routed
    assert '.ToUpper().StartsWith("!DELETEPIN")' not in routed


def test_private_link_interception_runs_before_generic_chat_and_remains_fail_closed():
    assert "[HarmonyPriority(Priority.First)]" in LINK
    prefix = method_body(LINK, "private static bool Prefix(ref ZRoutedRpc.RoutedRPCData data)")
    assert "IgnoredLinkClaimMethodHash" in prefix and "return false" in prefix and "return true" in prefix


def test_journal_is_name_free_and_join_leave_never_add_public_messages():
    assert "m_playerName" not in JOURNAL
    for class_name in ("private class ZNetPatchDisconnect", "private class ZRoutedRpcAddPeerPatch"):
        patch = WEBMAP[WEBMAP.index(class_name):]
        patch = patch[:patch.index("[HarmonyPatch", 1)]
        assert "m_playerName" not in patch and "peer != null" in patch and "peer.m_uid" in patch
    for signature, append, text in (("public void NotifyJoin", "QuorumActivityJournal.AppendJoin(peer)", "A player joined"), ("public void NotifyLeave", "QuorumActivityJournal.AppendLeave(peer)", "A player left")):
        body = method_body(WEBMAP, signature)
        assert text in body and "peer.m_playerName" not in body and "AddMessage" not in body and "BroadcastMessage" not in body
        if "SendMessage" in body: assert body.index(append) < body.index("SendMessage")


def test_webhook_is_removed_or_https_validated_bounded_async_and_disposable():
    if not WEBHOOK:
        assert "DiscordWebHook" not in WEBMAP
        return
    constructor = method_body(WEBHOOK, "public DiscordWebHook(string url)")
    assert "Uri.TryCreate" in constructor and "Uri.UriSchemeHttps" in constructor and "IsNullOrWhiteSpace" in constructor
    if "new WebClient" in constructor: assert constructor.index("Uri.TryCreate") < constructor.index("new WebClient")
    assert "BlockingCollection" in WEBHOOK or "Channel" in WEBHOOK
    assert "boundedCapacity" in WEBHOOK or "Capacity" in WEBHOOK
    assert "CancellationTokenSource" in WEBHOOK
    assert "Task.Run" in WEBHOOK or "new Thread" in WEBHOOK
    assert "UploadValues(" not in method_body(WEBHOOK, "public void SendMessage")
    assert "Timeout" in WEBHOOK and "Dispose" in WEBHOOK


def test_private_server_metadata_is_not_collected_or_serialized():
    assert "serverInfo" not in WEBMAP
    assert "SetServerInfo" not in WEBMAP
    for forbidden in ("worldSeed", "password", "openServer", "publicServer", "serverName"):
        assert forbidden not in WEBMAP
    owned = SERVER + WEBMAP + WEBHOOK
    for forbidden in ("ex.Message", "e.Message", "ex.ToString()", "e.ToString()", "GetServerIP", "HandleRoutedRPC:", "WebMap: (say)", "WebMap: (chat)", "WebMap: (ping)", "loading existing world: #", "old: #{currentWorldName}", "WORLD_START_POS.ToString()"):
        assert forbidden not in owned
    assert "console." not in "".join(path.read_text(encoding="utf-8") for path in (ROOT / "WebMap" / "web-src").glob("*.js"))
