from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recognized_link_claim_has_a_cross_patch_guard_before_webmap_reads_chat_data():
    claim = (ROOT / "WebMap" / "QuorumLinkClaimPatch.cs").read_text(encoding="utf-8")
    webmap = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")

    assert "EnterSuppression" in claim
    assert "IsSuppressed" in claim

    postfix_start = webmap.index("private static void Postfix(ref ZRoutedRpc __instance, ref RoutedRPCData data)")
    guard = webmap.index("QuorumLinkClaimPatch.IsSuppressed()", postfix_start)
    method_name_read = webmap.index("GetStableHashName", postfix_start)
    peer_read = webmap.index("ZNet.instance.GetPeer", postfix_start)

    assert guard < method_name_read
    assert guard < peer_read
