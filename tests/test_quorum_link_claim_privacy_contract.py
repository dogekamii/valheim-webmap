from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAIM = ROOT / "WebMap" / "QuorumLinkClaimPatch.cs"
JOURNAL = ROOT / "WebMap" / "QuorumActivityJournal.cs"
WEBMAP = ROOT / "WebMap" / "WebMap.cs"


def test_recognized_link_claim_is_diverted_before_existing_webmap_chat_postfix_reads_it():
    claim = CLAIM.read_text(encoding="utf-8")
    webmap = WEBMAP.read_text(encoding="utf-8")

    assert 'IgnoredLinkClaimMethodHash = "DestroyZDO".GetStableHashCode()' in claim
    match = claim.index("LinkCommand.Match(message)")
    divert = claim.index("data.m_methodHash = IgnoredLinkClaimMethodHash", match)
    assert match < divert

    postfix_start = webmap.index("private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)")
    ignore_guard = webmap.index("Array.Exists(ignoreRpc", postfix_start)
    peer_read = webmap.index("ZNet.instance.GetPeer", postfix_start)
    assert '"DestroyZDO"' in webmap
    assert ignore_guard < peer_read


def test_disabled_link_feature_leaves_link_text_on_the_ordinary_chat_path():
    claim = CLAIM.read_text(encoding="utf-8")

    gate = claim.index("if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)")
    parse = claim.index("new ZPackage", gate)
    assert gate < parse
    assert "return true;" in claim[gate:parse]


def test_recognized_claim_fails_closed_after_identity_or_journal_handling_fails():
    claim = CLAIM.read_text(encoding="utf-8")

    match = claim.index("LinkCommand.Match(message)")
    divert = claim.index("data.m_methodHash = IgnoredLinkClaimMethodHash", match)
    identity = claim.index("ZNet.instance", divert)
    journal = claim.index("QuorumActivityJournal.AppendLinkClaim", identity)
    suppress = claim.index("return false;", journal)
    assert match < divert < identity < journal < suppress
    assert "ZLog" not in claim


def test_link_claim_journal_contains_only_digest_not_code_or_player_name():
    journal = JOURNAL.read_text(encoding="utf-8")

    event_start = journal.index("private class LinkClaimEvent")
    event_end = journal.index("internal static void AppendJoin", event_start)
    event = journal[event_start:event_end]
    append_start = journal.index("internal static void AppendLinkClaim")
    append_end = journal.index("private static void Append(", append_start)
    append = journal[append_start:append_end]

    assert "code_sha256" in event
    assert "player_name" not in event
    assert "code_sha256 = Sha256(code)" in append
    assert "exception.Message" not in append
