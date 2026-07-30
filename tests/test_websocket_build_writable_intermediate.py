"""Regression contract for building immutable websocket source as an unprivileged user."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_xbuild_intermediates_are_redirected_out_of_the_read_only_source_tree():
    build = (ROOT / "build.cake").read_text(encoding="utf-8")
    source_task = build.split('Task("BuildWebsocketSharp")', 1)[1].split('var BuildTask = Task("Build")', 1)[0]
    assert "/property:IntermediateOutputPath=" in source_task
    assert "websocketBuildPath" in source_task
    assert "websocketSourceRoot}/obj" not in source_task
