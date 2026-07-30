import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DRAWDOWN = ROOT / "WebMap" / "web" / "drawdown.js"
JOURNAL = ROOT / "WebMap" / "QuorumActivityJournal.cs"
CONFIG = ROOT / "WebMap" / "Config.cs"
SERVER = ROOT / "WebMap" / "MapDataServer.cs"
PROJECT = ROOT / "WebMap" / "WebMap.csproj"
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"


def render_markdown(*inputs):
    runner = r"""
const fs = require('fs');
const vm = require('vm');
const context = {};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
const inputs = JSON.parse(process.argv[1]);
process.stdout.write(JSON.stringify(inputs.map(input => context.markdown(input))));
"""
    result = subprocess.run(
        ["node", "-e", runner, json.dumps(inputs), str(DRAWDOWN)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_chat_markdown_rejects_script_urls_and_attribute_injection():
    image, script_link, safe_link = render_markdown(
        '![x](safe.png" onerror="alert(1))',
        "[x](javascript:alert(1))",
        "[safe](https://example.invalid/path?q=1&x=2)",
    )

    assert "<img" not in image
    assert "onerror" not in image.lower()
    assert "<a" not in script_link
    assert "javascript:" not in script_link.lower()
    assert '<a href="https://example.invalid/path?q=1&amp;x=2">safe</a>' in safe_link


def test_activity_journal_is_private_before_the_first_record_is_written():
    journal = JOURNAL.read_text(encoding="utf-8")

    open_stream = journal.index("new FileStream")
    restrict = journal.index("chmod(path, JournalFileMode)", open_stream)
    write = journal.index("WriteLine(json)", restrict)
    assert open_stream < restrict < write
    assert re.search(r"JournalFileMode\s*=\s*0x180", journal)
    assert "File.AppendAllText" not in journal


def test_activity_journal_minimizes_new_records_and_preserves_existing_lines():
    journal = JOURNAL.read_text(encoding="utf-8")
    event_match = re.search(
        r"private class ActivityEvent\s*\{(?P<body>.*?)\n\s*\}", journal, re.DOTALL
    )

    assert event_match is not None
    fields = re.findall(
        r"public\s+(?:string|long)\s+(\w+);", event_match.group("body")
    )
    assert fields == ["type", "player_id", "occurred_at_unix"]
    assert "peer.m_playerName" not in journal
    assert "FileMode.Append" in journal


def test_activity_journal_failures_never_log_exception_details():
    journal = JOURNAL.read_text(encoding="utf-8")

    assert "exception.Message" not in journal
    assert "ex.Message" not in journal
    assert "exception.ToString" not in journal
    assert "ex.ToString" not in journal


def test_test_setting_does_not_overwrite_debug_setting():
    config = CONFIG.read_text(encoding="utf-8")

    assert 'TEST = config.Bind("Server", "test"' in config
    assert config.count('DEBUG = config.Bind("Server", "debug"') == 1
    assert config.count('DEBUG = config.Bind("Server", "test"') == 0


def test_websocket_connection_log_does_not_collect_remote_endpoints():
    server = SERVER.read_text(encoding="utf-8")

    assert 'Context.Headers.Get("X-Forwarded-For")' not in server
    assert "Context.UserEndPoint" not in server
    assert "new visitor connected from" not in server


def test_messages_route_uses_the_json_content_type():
    server = SERVER.read_text(encoding="utf-8")

    assert 'res.ContentType = "application/json";' in server
    assert "applicaion/json" not in server


def test_compile_only_game_references_are_not_release_payload_dependencies():
    project = ET.parse(PROJECT).getroot()
    references = {
        reference.attrib["Include"]: reference
        for reference in project.findall(".//Reference")
    }
    compile_only = {
        "0Harmony",
        "BepInEx",
        "BepInEx.Harmony",
        "assembly_valheim",
        "assembly_utils",
        "Mono.Security",
        "UnityEngine",
        "UnityEngine.CoreModule",
        "UnityEngine.JSONSerializeModule",
        "Splatform",
        "steamworks",
    }

    for name in compile_only:
        assert references[name].findtext("Private") == "false", name
    assert references["WebsocketSharp"].findtext("Private") == "true"

    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Reject compile-only DLLs from release output" in workflow
    assert "! -name 'WebMap.dll'" in workflow
    assert "! -name 'websocket-sharp.dll'" in workflow
