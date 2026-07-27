from pathlib import Path

source = (Path(__file__).parents[1] / "WebMap" / "WebMap.cs").read_text()

# Current Valheim calls ZNet.WorldSetup() for both an existing .db world and
# a newly-created world. ZoneSystem.Load() is skipped for the latter.
assert '[HarmonyPatch(typeof(ZNet), "WorldSetup")]' in source, (
    "WebMap must initialize from ZNet.WorldSetup, not only ZoneSystem.Load"
)
assert 'ZoneSystemLoadPatch' not in source, "obsolete ZoneSystem.Load patch must be removed"
assert 'StartMapServerOnce' in source, "world-ready startup must be idempotent"

# Current Unity ships ImageConversion in a netstandard2.1 module. Keep the
# net48 BepInEx plugin binary compatible by resolving those APIs at runtime.
assert '.EncodeToPNG()' not in source, "do not compile directly against ImageConversionModule"
assert '.LoadImage(' not in source, "do not compile directly against ImageConversionModule"
assert 'EncodeTextureToPng' in source
assert 'LoadTextureFromImage' in source

project = (Path(__file__).parents[1] / "WebMap" / "WebMap.csproj").read_text()
assert 'UnityEngine.ImageConversionModule' not in project, (
    "net48 plugin must not reference the current netstandard2.1 image module"
)
