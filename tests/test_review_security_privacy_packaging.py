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
    result = subprocess.run(["node", "-e", runner, json.dumps(inputs), str(DRAWDOWN)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_chat_markdown_rejects_script_urls_and_attribute_injection():
    image, script_link, safe_http_link, safe_https_link = render_markdown(
        '![x](safe.png" onerror="alert(1))', "[x](javascript:alert(1))",
        "[http](http://example.invalid/path)", "[https](https://example.invalid/path?q=1&x=2)")
    assert "<img" not in image and "onerror" not in image.lower()
    assert "<a" not in script_link and "javascript:" not in script_link.lower()
    assert '<a href="http://example.invalid/path">http</a>' in safe_http_link
    assert '<a href="https://example.invalid/path?q=1&amp;x=2">https</a>' in safe_https_link


def test_chat_markdown_images_only_use_same_origin_relative_paths():
    rendered = render_markdown("![root](/images/map.png)", "![path](images/map.png?x=1&y=2)", "![dot](./mapIcons.png)",
        "![protocol-relative](//tracker.invalid/pixel.png)", "![https](https://tracker.invalid/pixel.png)",
        "![http](http://tracker.invalid/pixel.png)", "![data](data:image/svg+xml,boom)",
        "![script](javascript:alert(1))", "![control](/images/safe\u0001.png)",
        "![tab](/images/safe\t.png)", r"![backslash](\\tracker.invalid\pixel.png)")
    assert '<img src="/images/map.png" alt="root"/>' in rendered[0]
    assert '<img src="images/map.png?x=1&amp;y=2" alt="path"/>' in rendered[1]
    assert '<img src="./mapIcons.png" alt="dot"/>' in rendered[2]
    for unsafe in rendered[3:]: assert "<img" not in unsafe


def test_activity_journal_is_group_readable_before_the_first_record_is_written():
    journal = JOURNAL.read_text(encoding="utf-8")
    open_stream = journal.index("new FileStream")
    restrict = journal.index("chmod(path, JournalFileMode)", open_stream)
    write = journal.index("WriteLine(json)", restrict)
    assert open_stream < restrict < write
    assert re.search(r"JournalFileMode\s*=\s*0x1A0", journal)
    assert "0640" in journal and "owner read/write" in journal and "designated group read" in journal and "1000:1000" in journal
    assert "File.AppendAllText" not in journal


def test_activity_journal_minimizes_new_records_and_preserves_existing_lines():
    journal = JOURNAL.read_text(encoding="utf-8")
    event_match = re.search(r"private class ActivityEvent\s*\{(?P<body>.*?)\n\s*\}", journal, re.DOTALL)
    assert event_match is not None
    fields = re.findall(r"public\s+(?:string|long)\s+(\w+);", event_match.group("body"))
    assert fields == ["type", "player_id", "occurred_at_unix"]
    assert "peer.m_playerName" not in journal and "FileMode.Append" in journal


def test_activity_journal_failures_never_log_exception_details():
    journal = JOURNAL.read_text(encoding="utf-8")
    for forbidden in ("exception.Message", "ex.Message", "exception.ToString", "ex.ToString"): assert forbidden not in journal


def test_test_setting_does_not_overwrite_debug_setting():
    config = CONFIG.read_text(encoding="utf-8")
    assert 'TEST = config.Bind("Server", "test"' in config
    assert config.count('DEBUG = config.Bind("Server", "debug"') == 1
    assert config.count('DEBUG = config.Bind("Server", "test"') == 0


def test_websocket_connection_log_does_not_collect_remote_endpoints():
    server = SERVER.read_text(encoding="utf-8")
    assert 'Context.Headers.Get("X-Forwarded-For")' not in server
    assert "Context.UserEndPoint" not in server and "new visitor connected from" not in server


def test_messages_route_is_not_public():
    server = SERVER.read_text(encoding="utf-8")
    for forbidden in ('case "/messages"', "MapMessage", "BroadcastMessage", "sentMessages"): assert forbidden not in server


def test_http_security_headers_cover_special_static_and_error_responses():
    server = SERVER.read_text(encoding="utf-8")
    on_get = server.index("httpServer.OnGet")
    apply_headers = server.index("ApplySecurityHeaders(e.Response)", on_get)
    special_routes = server.index("ProcessSpecialRoutes(e)", apply_headers)
    static_files = server.index("ServeStaticFiles(e)", special_routes)
    assert on_get < apply_headers < special_routes < static_files
    for name, value in (("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
                        ("X-Frame-Options", "DENY"), ("Content-Security-Policy", "ContentSecurityPolicy")):
        assert name in server and value in server


def test_content_security_policy_allows_only_required_browser_sources():
    server = SERVER.read_text(encoding="utf-8")
    match = re.search(r'ContentSecurityPolicy\s*=\s*"(?P<value>[^"]+)";', server)
    assert match is not None
    directives = {parts[0]: parts[1:] for directive in match.group("value").split(";") if (parts := directive.strip().split())}
    assert directives["default-src"] == ["'self'"]
    assert directives["script-src"] == ["'self'"]
    assert directives["style-src"] == ["'self'", "'unsafe-inline'"]
    assert directives["connect-src"] == ["'self'"]
    assert directives["img-src"] == ["'self'", "data:"]
    assert directives["object-src"] == ["'none'"]
    assert directives["base-uri"] == ["'self'"]
    assert directives["frame-ancestors"] == ["'none'"]
    assert "'unsafe-inline'" not in directives["script-src"]
    assert "http:" not in match.group("value") and "https:" not in match.group("value")


def test_workflow_is_least_privilege_pinned_and_not_duplicated_on_pr_pushes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "branches: [main]" in workflow and "branches: ['**']" not in workflow and "pull_request:" in workflow
    assert "permissions:\n  contents: read\n" in workflow
    assert "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4" in workflow
    assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5" in workflow
    assert "actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4" in workflow
    assert "actions/checkout@v4" not in workflow and "actions/setup-python@v5" not in workflow and "actions/setup-node@v4" not in workflow
    assert "run: npm audit" in workflow


def test_compile_only_game_references_are_not_release_payload_dependencies():
    project = ET.parse(PROJECT).getroot()
    references = {reference.attrib["Include"]: reference for reference in project.findall(".//Reference")}
    compile_only = {"0Harmony", "BepInEx", "BepInEx.Harmony", "assembly_valheim", "assembly_utils", "Mono.Security", "UnityEngine", "UnityEngine.CoreModule", "UnityEngine.JSONSerializeModule", "Splatform", "steamworks"}
    for name in compile_only: assert references[name].findtext("Private") == "false", name
    assert references["WebsocketSharp"].findtext("Private") == "true"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Reject compile-only DLLs from release output" in workflow
    assert "! -name 'WebMap.dll'" in workflow and "! -name 'websocket-sharp.dll'" in workflow
