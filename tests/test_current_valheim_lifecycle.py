from pathlib import Path

source = (Path(__file__).parents[1] / "WebMap" / "WebMap.cs").read_text()

# Current Valheim calls ZNet.WorldSetup() for both an existing .db world and
# a newly-created world. ZoneSystem.Load() is skipped for the latter.
assert '[HarmonyPatch(typeof(ZNet), "WorldSetup")]' in source, (
    "WebMap must initialize from ZNet.WorldSetup, not only ZoneSystem.Load"
)
assert 'ZoneSystemLoadPatch' not in source, "obsolete ZoneSystem.Load patch must be removed"
assert 'StartMapServerOnce' in source, "world-ready startup must be idempotent"
