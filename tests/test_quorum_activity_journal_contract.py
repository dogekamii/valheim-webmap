from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_quorum_activity_journal_is_private_opt_in_and_lifecycle_bound():
    config = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
    plugin = (ROOT / "WebMap" / "WebMap.cs").read_text(encoding="utf-8")
    journal = (ROOT / "WebMap" / "QuorumActivityJournal.cs").read_text(encoding="utf-8")

    assert "QUORUM_ACTIVITY_JOURNAL_ENABLED = false" in config
    assert 'config.Bind("Quorum Bot", "activity_journal_enabled"' in config
    assert "QuorumActivityJournal.AppendJoin(peer)" in plugin
    assert "QuorumActivityJournal.AppendLeave(peer)" in plugin
    assert "if (!WebMapConfig.QUORUM_ACTIVITY_JOURNAL_ENABLED)" in journal
    assert "Path.Combine(WebMap.worldDataPath, \"quorum_activity.jsonl\")" in journal
    assert '"join"' in journal and '"leave"' in journal
    assert "discord" not in journal.lower()
    assert "http" not in journal.lower()
