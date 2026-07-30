import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "WebMap" / "MapDataServer.cs").read_text(encoding="utf-8")
CONFIG = (ROOT / "WebMap" / "Config.cs").read_text(encoding="utf-8")
BROWSER_MAP = (ROOT / "WebMap" / "web-src" / "map.js").read_text(encoding="utf-8")


def method_body(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1:index]
    raise AssertionError(f"unterminated method: {signature}")


def constant(source, name):
    match = re.search(rf"const int {name}\s*=\s*(\d+);", source)
    assert match is not None, name
    return int(match.group(1))


def test_map_query_is_exactly_one_case_sensitive_digest_pair():
    route = method_body(SERVER, "private bool ProcessSpecialRoutes")
    assert "req.QueryString.Count != 1" in route
    assert "req.QueryString.AllKeys[0]" in route
    assert 'string.Equals(req.QueryString.AllKeys[0], "v", StringComparison.Ordinal)' in route
    assert 'req.QueryString.GetValues("v")' in route
    assert "values.Length != 1" in route
    assert "IsValidMapDigest(values[0])" in route
    assert "FixedTimeEquals(values[0], publication.Digest)" in route


def test_world_start_coordinates_are_finite_bounded_immediately_before_serialization():
    serializer = method_body(CONFIG, "public static string MakeClientConfigJson")
    assert "SanitizeMapCoordinate(WORLD_START_POS.x)" in serializer
    assert "SanitizeMapCoordinate(WORLD_START_POS.z)" in serializer
    sanitizer = method_body(CONFIG, "private static float SanitizeMapCoordinate")
    assert "float.IsNaN" in sanitizer and "float.IsInfinity" in sanitizer
    assert "MaxMapCoordinate" in sanitizer
    assert "return 0f" in sanitizer
    assert serializer.index("SanitizeMapCoordinate") < serializer.index("JsonUtility.ToJson")


def test_private_pin_identity_snapshot_and_browser_work_share_a_total_cap():
    server_cap = constant(SERVER, "MaxPrivatePins")
    identity_cap = constant(SERVER, "MaxPublicIdentities")
    browser_cap_match = re.search(r"const MAX_MAP_ICONS\s*=\s*(\d+);", BROWSER_MAP)
    assert browser_cap_match is not None
    browser_cap = int(browser_cap_match.group(1))
    assert 0 < server_cap <= 5000
    assert identity_cap == server_cap
    assert browser_cap == server_cap

    replace = method_body(SERVER, "public void ReplacePins")
    assert "privatePins.Count >= MaxPrivatePins" in replace
    assert "break" in replace
    add = method_body(SERVER, "public void AddPin")
    assert add.index("privatePins.Count >= MaxPrivatePins") < add.index("privatePins.Add(record)")
    identity = method_body(SERVER, "internal static bool TryForOwner")
    assert "Identities.Count >= MaxPublicIdentities" in identity
    assert "return false" in identity
    serializer = method_body(SERVER, "private static bool TrySerializePublicPin")
    assert "PublicIdentity.TryForOwner" in serializer


def test_failed_construction_or_server_start_cannot_publish_a_partial_singleton():
    constructor = method_body(SERVER, "public MapDataServer(WebMap owner)")
    assert constructor.index("owner.StartCoroutine") < constructor.index("__instance = this")
    start = method_body(SERVER, "public void ListenAsync")
    catch_body = start[start.index("catch"):]
    assert "Stop()" in catch_body
    assert "WebMap.mapDataServer = null" in catch_body
    assert "throw;" in catch_body
