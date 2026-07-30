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
CI_REQUIREMENTS = ROOT / "requirements-ci.txt"


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
    expected = {
        "actions/checkout": {("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1")},
        "actions/setup-python": {("5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0")},
        "actions/setup-node": {("820762786026740c76f36085b0efc47a31fe5020", "v7.0.0")},
    }
    found = {}
    for action, commit, tag in re.findall(
        r"uses:\s+(actions/(?:checkout|setup-python|setup-node))@([0-9a-f]{40})\s+#\s+(v\S+)", workflow
    ):
        found.setdefault(action, set()).add((commit, tag))
    assert found == expected
    assert not re.search(r"uses:\s+actions/(?:checkout|setup-python|setup-node)@v", workflow)
    assert "run: npm audit" in workflow


def test_workflow_pins_python_and_installs_only_the_hash_locked_ci_closure():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "python-version: '3.11.15'" in workflow
    command = (
        "python -m pip install --disable-pip-version-check --require-hashes "
        "--no-deps --requirement requirements-ci.txt"
    )
    assert command in workflow
    assert not re.search(r"pip install[^\n]*\bpytest\b", workflow)


def test_ci_requirements_lock_is_exact_complete_and_hash_locked():
    assert CI_REQUIREMENTS.is_file(), "requirements-ci.txt must be committed"
    logical_lines = []
    current = ""
    for raw_line in CI_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        current = f"{current} {line}".strip()
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        logical_lines.append(current)
        current = ""
    assert not current

    actual = {}
    for line in logical_lines:
        tokens = line.split()
        name, version = tokens[0].split("==", 1)
        hashes = {
            token.removeprefix("--hash=sha256:")
            for token in tokens[1:]
            if token.startswith("--hash=sha256:")
        }
        assert len(hashes) == 2
        assert len(tokens) == 1 + len(hashes)
        actual[name.lower()] = (version, hashes)

    expected = {
        "iniconfig": ("2.3.0", {
            "f631c04d2c48c52b84d0d0549c99ff3859c98df65b3101406327ecc7d53fbf12",
            "c76315c77db068650d49c5b56314774a7804df16fee4402c1f19d6d15d8c4730",
        }),
        "packaging": ("26.2", {
            "5fc45236b9446107ff2415ce77c807cee2862cb6fac22b8a73826d0693b0980e",
            "ff452ff5a3e828ce110190feff1178bb1f2ea2281fa2075aadb987c2fb221661",
        }),
        "pluggy": ("1.6.0", {
            "e920276dd6813095e9377c0bc5566d94c932c33b27a3e3945d8389c374dd4746",
            "7dcc130b76258d33b90f61b658791dede3486c3e6bfb003ee5c9bfb396dd22f3",
        }),
        "pygments": ("2.20.0", {
            "81a9e26dd42fd28a23a2d169d86d7ac03b46e2f8b59ed4698fb4785f946d0176",
            "6757cd03768053ff99f3039c1a36d6c0aa0b263438fcab17520b30a303a82b5f",
        }),
        "pytest": ("9.1.1", {
            "37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c",
            "1088fbde8f2b49d95a549a195707afa7a76a3ce9bcadc26b6d71f0ffda5fe313",
        }),
    }
    assert actual == expected


def test_compile_only_game_references_are_not_release_payload_dependencies():
    project = ET.parse(PROJECT).getroot()
    references = {reference.attrib["Include"]: reference for reference in project.findall(".//Reference")}
    compile_only = {"0Harmony", "BepInEx", "BepInEx.Harmony", "assembly_valheim", "assembly_utils", "Mono.Security", "UnityEngine", "UnityEngine.CoreModule", "UnityEngine.JSONSerializeModule", "Splatform", "steamworks"}
    for name in compile_only: assert references[name].findtext("Private") == "false", name
    assert references["WebsocketSharp"].findtext("Private") == "true"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "Reject compile-only DLLs from release output" in workflow
    assert "! -name 'WebMap.dll'" in workflow and "! -name 'websocket-sharp.dll'" in workflow
