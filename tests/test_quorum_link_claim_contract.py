from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_link_claim_is_suppressed_hashed_and_local_only():
    patch = (ROOT / "WebMap" / "QuorumLinkClaimPatch.cs").read_text(encoding="utf-8")
    journal = (ROOT / "WebMap" / "QuorumActivityJournal.cs").read_text(encoding="utf-8")

    assert "private static bool Prefix" in patch
    assert "!LINK" in patch
    assert "QuorumActivityJournal.AppendLinkClaim(peer, code)" in patch
    assert "return false" in patch
    assert '"link_claim"' in journal
    assert "code_sha256" in journal
    assert "SHA256" in journal
    assert "discord" not in journal.lower()
    assert "http" not in journal.lower()
