#!/usr/bin/env bash
set -euo pipefail
archive="${1:-dist/valheim-webmap-2.7.4.zip}"
compiler_output="WebMap/bin/Release/net48"
source_built_dependency="${WEBSOCKET_SHARP_BUILD_OUTPUT:-/tmp/websocket-sharp-build/websocket-sharp.dll}"
opaque_hash="33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244"
notice_name="THIRD-PARTY-NOTICES.txt"

python3 scripts/inspect-release-archive.py "$archive" \
    --source-built "$source_built_dependency" \
    --compiler-output "$compiler_output"

extract_root="$(mktemp -d)"
trap 'rm -rf "$extract_root"' EXIT
python3 - "$archive" "$extract_root" <<'PY'
from pathlib import Path
import sys
import zipfile
archive, destination = sys.argv[1:]
with zipfile.ZipFile(archive, "r") as source:
    source.extractall(Path(destination))
PY
package="$extract_root/WebMap"

mapfile -t dlls < <(find "$package" -maxdepth 1 -type f -name '*.dll' -print | sort)
if [[ ${#dlls[@]} -ne 2 ]] || [[ ! -s "$package/WebMap.dll" ]] || [[ ! -s "$package/websocket-sharp.dll" ]]; then
    echo "privacy inspection failed: expected exactly two archive DLLs" >&2
    exit 1
fi
if [[ ! -s "$source_built_dependency" ]] || ! cmp -s "$source_built_dependency" "$package/websocket-sharp.dll"; then
    echo "privacy inspection failed: archived websocket-sharp.dll is not the current source-build output" >&2
    exit 1
fi

mapfile -t bundles < <(find "$package/web" -maxdepth 1 -type f -name 'main.*.js' -size +0c -printf '%f\n')
if [[ ${#bundles[@]} -ne 1 ]] || [[ ! "${bundles[0]}" =~ ^main\.[0-9a-f]{16}\.js$ ]] || [[ -e "$package/web/main.js" ]]; then
    echo "privacy inspection failed: expected one archived main.[0-9a-f]{16}.js and no main.js" >&2
    exit 1
fi

if [[ ! -s "$package/$notice_name" ]]; then
    echo "privacy inspection failed: archived third-party notice missing" >&2
    exit 1
fi
for required in \
    'https://github.com/sta/websocket-sharp' \
    '4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1' \
    '310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a' \
    'Permission is hereby granted, free of charge' \
    'THE SOFTWARE IS PROVIDED "AS IS"' \
    'built from'; do
    if ! grep -Fq -- "$required" "$package/$notice_name"; then
        echo "privacy inspection failed: incomplete archived third-party notice" >&2
        exit 1
    fi
done
if grep -Eiq 'unverified|unresolved' "$package/$notice_name"; then
    echo "privacy inspection failed: stale unresolved dependency provenance wording" >&2
    exit 1
fi

actual_hash="$(sha256sum "$package/websocket-sharp.dll" | awk '{print $1}')"
if [[ "$actual_hash" == "$opaque_hash" ]]; then
    echo "privacy inspection failed: websocket-sharp.dll must not match removed opaque repository DLL" >&2
    exit 1
fi
assembly_metadata="$(monodis --assembly "$package/websocket-sharp.dll")"
assembly_name="$(awk '$1 == "Name:" { print $2 }' <<<"$assembly_metadata")"
assembly_version="$(awk '$1 == "Version:" { print $2 }' <<<"$assembly_metadata")"
public_key_output="$(sn -T "$package/websocket-sharp.dll" 2>&1)"
if [[ "$assembly_name" != "websocket-sharp" ]] || [[ "$assembly_version" != "1.0.2.29017" ]]; then
    echo "privacy inspection failed: unexpected websocket-sharp assembly name/version" >&2
    exit 1
fi
if ! grep -Fqi '5660b08a1845a91e' <<<"$public_key_output" || ! sn -vf "$package/websocket-sharp.dll" >/dev/null 2>&1; then
    echo "privacy inspection failed: websocket-sharp strong name is missing or incompatible" >&2
    exit 1
fi
artifact_size="$(stat -c '%s' "$package/websocket-sharp.dll")"
toolchain="$(dpkg-query -W -f='${Version}' mono-devel)"

runtime_sources=(WebMap/MapDataServer.cs WebMap/WebMap.cs WebMap/Config.cs)
telemetry_tokens=('MapMessage' 'BroadcastMessage' 'BroadcastPing' '/messages' 'messages\n' 'ping\n' 'max_health' 'm_playerName' 'm_publicRefPos' 'inBed' 'ServerClient' 'AddExtraPlayer' 'SendPlayerList' 'worldSeed' 'password' 'openServer' 'publicServer' 'serverInfo' 'serverName' 'world_name')
for token in "${telemetry_tokens[@]}"; do
    if grep -aFq -- "$token" "${runtime_sources[@]}"; then
        echo "privacy inspection failed: public source retains telemetry or private metadata" >&2
        exit 1
    fi
done

for token in 'MapMessage' 'BroadcastMessage' 'BroadcastPing' 'AddExtraPlayer' 'SendPlayerList'; do
    if grep -aFq -- "$token" "$package/WebMap.dll"; then
        echo "privacy inspection failed: compiled public telemetry symbol" >&2
        exit 1
    fi
done

bundle="$package/web/${bundles[0]}"
for token in 'playerMapIcons' 'followPlayer' 'followIcon' 'setFollowIcon' 'centerOnIcon' 'maxHealth' 'health' 'messages\n' 'ping\n' 'world_name' 'worldSeed' 'password' 'openServer' 'publicServer' 'serverInfo' 'serverName'; do
    if grep -aFq -- "$token" "$bundle"; then
        echo "privacy inspection failed: browser telemetry or private metadata symbol" >&2
        exit 1
    fi
done
for required in 'online' 'map_digest'; do
    if ! grep -aFq -- "$required" "${runtime_sources[@]}" || ! grep -aFq -- "$required" "$bundle"; then
        echo "privacy inspection failed: required aggregate/map protocol missing" >&2
        exit 1
    fi
done
if ! grep -aFq -- 'map_digest' "$package/WebMap.dll"; then
    echo "privacy inspection failed: compiled map protocol missing" >&2
    exit 1
fi

echo "source-built websocket-sharp.dll: sha256=$actual_hash size=$artifact_size identity=websocket-sharp,Version=1.0.2.29017,PublicKeyToken=5660b08a1845a91e mono-devel=$toolchain"
echo "::notice file=docs/DEPENDENCY_PROVENANCE.md,line=1::source-built websocket-sharp.dll sha256=$actual_hash size=$artifact_size identity=websocket-sharp,Version=1.0.2.29017,PublicKeyToken=5660b08a1845a91e mono-devel=$toolchain"
echo "release archive privacy inspection passed"
