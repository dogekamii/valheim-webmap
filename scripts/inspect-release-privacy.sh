#!/usr/bin/env bash
set -euo pipefail

output="WebMap/bin/Release/net48"
mapfile -t dlls < <(find "$output" -maxdepth 1 -type f -name '*.dll' -print | sort)
if [[ ${#dlls[@]} -ne 2 ]] || [[ ! -s "$output/WebMap.dll" ]] || [[ ! -s "$output/websocket-sharp.dll" ]]; then
    echo "privacy inspection failed: expected exactly two DLLs" >&2
    exit 1
fi

mapfile -t bundles < <(find WebMap/web -maxdepth 1 -type f -name 'main.*.js' -size +0c -print)
if [[ ${#bundles[@]} -ne 1 ]]; then
    echo "privacy inspection failed: expected one main.*.js" >&2
    exit 1
fi

for token in 'MapMessage' 'BroadcastMessage' 'BroadcastPing' '/messages' 'messages\n' 'ping\n' 'max_health' 'm_playerName' 'm_publicRefPos' 'inBed'; do
    if grep -aFq -- "$token" "$output/WebMap.dll"; then
        echo "privacy inspection failed: server telemetry symbol" >&2
        exit 1
    fi
done

for token in 'playerMapIcons' 'followPlayer' 'maxHealth' 'messages\n' 'ping\n'; do
    if grep -aFq -- "$token" "${bundles[0]}"; then
        echo "privacy inspection failed: browser telemetry symbol" >&2
        exit 1
    fi
done

echo "release privacy inspection passed"
