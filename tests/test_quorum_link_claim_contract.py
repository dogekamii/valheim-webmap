from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_link_claim_is_suppressed_hashed_and_local_only():
    plugin = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")
    journal = (ROOT / "WebMap" / "QuorumActivityJournal.cs").read_text(encoding="utf-8")

    assert "ZRoutedRpcPatch" in plugin
    assert "private static bool Prefix" in plugin
    assert "!LINK" in plugin
    assert "QuorumActivityJournal.AppendLinkClaim(peer, code)" in plugin
    assert "return false" in plugin
    assert '"link_claim"' in journal
    assert "code_sha256" in journal
    assert "SHA256" in journal
    assert "discord" not in journal.lower()
    assert "http" not in journal.lower()
