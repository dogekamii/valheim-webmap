#!/usr/bin/env bash
set -euo pipefail
output="WebMap/bin/Release/net48"
mapfile -t dlls < <(find "$output" -maxdepth 1 -type f -name '*.dll' -print | sort)
if [[ ${#dlls[@]} -ne 2 ]] || [[ ! -s "$output/WebMap.dll" ]] || [[ ! -s "$output/websocket-sharp.dll" ]]; then
    echo "privacy inspection failed: expected exactly two DLLs" >&2
    exit 1
fi
mapfile -t bundles < <(find WebMap/web -maxdepth 1 -type f -name 'main.*.js' -size +0c -print)
if [[ ${#bundles[@]} -ne 1 ]] || [[ -e WebMap/web/main.js ]]; then
    echo "privacy inspection failed: expected one hashed main.*.js and no main.js" >&2
    exit 1
fi

runtime_sources=(WebMap/MapDataServer.cs WebMap/WebMap.cs WebMap/Config.cs)
telemetry_tokens=('MapMessage' 'BroadcastMessage' 'BroadcastPing' '/messages' 'messages\n' 'ping\n' 'max_health' 'm_playerName' 'm_publicRefPos' 'inBed' 'ServerClient' 'AddExtraPlayer' 'SendPlayerList' 'worldSeed' 'password' 'openServer' 'publicServer' 'serverInfo' 'serverName' 'world_name')
for token in "${telemetry_tokens[@]}"; do
    if grep -aFq -- "$token" "${runtime_sources[@]}"; then
        echo "privacy inspection failed: public source retains telemetry or private metadata" >&2
        exit 1
    fi
done

# Game/framework TypeRef and MemberRef names can occur in a managed DLL without
# being serialized or reachable from the public protocol. Inspect those names in
# owned source above; reserve binary symbol rejection for unambiguous WebMap
# telemetry types/methods so harmless compiler metadata cannot fail a release.
for token in 'MapMessage' 'BroadcastMessage' 'BroadcastPing' 'AddExtraPlayer' 'SendPlayerList'; do
    if grep -aFq -- "$token" "$output/WebMap.dll"; then
        echo "privacy inspection failed: compiled public telemetry symbol" >&2
        exit 1
    fi
done

for token in 'playerMapIcons' 'followPlayer' 'followIcon' 'setFollowIcon' 'centerOnIcon' 'maxHealth' 'health' 'messages\n' 'ping\n' 'world_name' 'worldSeed' 'password' 'openServer' 'publicServer' 'serverInfo' 'serverName'; do
    if grep -aFq -- "$token" "${bundles[0]}"; then
        echo "privacy inspection failed: browser telemetry or private metadata symbol" >&2
        exit 1
    fi
done
for required in 'online' 'map_digest'; do
    if ! grep -aFq -- "$required" "${runtime_sources[@]}" || ! grep -aFq -- "$required" "${bundles[0]}"; then
        echo "privacy inspection failed: required aggregate/map protocol missing" >&2
        exit 1
    fi
done
if ! grep -aFq -- 'map_digest' "$output/WebMap.dll"; then
    echo "privacy inspection failed: compiled map protocol missing" >&2
    exit 1
fi
echo "release privacy inspection passed"
