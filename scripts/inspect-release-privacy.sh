#!/usr/bin/env bash
set -euo pipefail
output="WebMap/bin/Release/net48"
source_built_dependency="${WEBSOCKET_SHARP_BUILD_OUTPUT:-/tmp/websocket-sharp-build/websocket-sharp.dll}"
opaque_hash="33c2b65512e71a0c05cbe1c2f89343605653e5f7fada91885ba756b12121b244"
notice_name="THIRD-PARTY-NOTICES.txt"

mapfile -t entries < <(find "$output" -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)
if [[ ${#entries[@]} -ne 4 ]]; then
    echo "privacy inspection failed: expected exactly four release files" >&2
    exit 1
fi
mapfile -t dlls < <(find "$output" -maxdepth 1 -type f -name '*.dll' -print | sort)
if [[ ${#dlls[@]} -ne 2 ]] || [[ ! -s "$output/WebMap.dll" ]] || [[ ! -s "$output/websocket-sharp.dll" ]]; then
    echo "privacy inspection failed: expected exactly two DLLs" >&2
    exit 1
fi
if [[ ! -s "$source_built_dependency" ]] || ! cmp -s "$source_built_dependency" "$output/websocket-sharp.dll"; then
    echo "privacy inspection failed: packaged websocket-sharp.dll is not the current source-build output" >&2
    exit 1
fi

mapfile -t bundles < <(find "$output" -maxdepth 1 -type f -name 'main.*.js' -size +0c -printf '%f\n')
if [[ ${#bundles[@]} -ne 1 ]] || [[ ! "${bundles[0]}" =~ ^main\.[0-9a-f]{16}\.js$ ]] || [[ -e "$output/main.js" ]]; then
    echo "privacy inspection failed: expected one main.[0-9a-f]{16}.js and no main.js" >&2
    exit 1
fi
expected_entries=("THIRD-PARTY-NOTICES.txt" "WebMap.dll" "${bundles[0]}" "websocket-sharp.dll")
IFS=$'\n' expected_entries=($(printf '%s\n' "${expected_entries[@]}" | sort)); unset IFS
if [[ "${entries[*]}" != "${expected_entries[*]}" ]]; then
    echo "privacy inspection failed: release allowlist mismatch" >&2
    exit 1
fi

if [[ ! -s "$output/$notice_name" ]]; then
    echo "privacy inspection failed: third-party notice missing" >&2
    exit 1
fi
for required in \
    'https://github.com/sta/websocket-sharp' \
    '4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1' \
    '310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a' \
    'Permission is hereby granted, free of charge' \
    'THE SOFTWARE IS PROVIDED "AS IS"' \
    'built from'; do
    if ! grep -Fq -- "$required" "$output/$notice_name"; then
        echo "privacy inspection failed: incomplete third-party notice" >&2
        exit 1
    fi
done
if grep -Eiq 'unverified|unresolved' "$output/$notice_name"; then
    echo "privacy inspection failed: stale unresolved dependency provenance wording" >&2
    exit 1
fi

actual_hash="$(sha256sum "$output/websocket-sharp.dll" | awk '{print $1}')"
if [[ "$actual_hash" == "$opaque_hash" ]]; then
    echo "privacy inspection failed: websocket-sharp.dll must not match removed opaque repository DLL" >&2
    exit 1
fi
assembly_metadata="$(monodis --assembly "$output/websocket-sharp.dll")"
assembly_name="$(awk '$1 == "Name:" { print $2 }' <<<"$assembly_metadata")"
assembly_version="$(awk '$1 == "Version:" { print $2 }' <<<"$assembly_metadata")"
public_key_output="$(sn -T "$output/websocket-sharp.dll" 2>&1)"
if [[ "$assembly_name" != "websocket-sharp" ]] || [[ "$assembly_version" != "1.0.2.29017" ]]; then
    echo "privacy inspection failed: unexpected websocket-sharp assembly name/version" >&2
    exit 1
fi
if ! grep -Fqi '5660b08a1845a91e' <<<"$public_key_output" || ! sn -vf "$output/websocket-sharp.dll" >/dev/null 2>&1; then
    echo "privacy inspection failed: websocket-sharp strong name is missing or incompatible" >&2
    exit 1
fi
artifact_size="$(stat -c '%s' "$output/websocket-sharp.dll")"
toolchain="$(dpkg-query -W -f='${Version}' mono-devel)"
echo "source-built websocket-sharp.dll: sha256=$actual_hash size=$artifact_size identity=websocket-sharp,Version=1.0.2.29017,PublicKeyToken=5660b08a1845a91e mono-devel=$toolchain"
if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
    echo "::notice file=docs/DEPENDENCY_PROVENANCE.md,line=1::source-built websocket-sharp.dll sha256=$actual_hash size=$artifact_size identity=websocket-sharp,Version=1.0.2.29017,PublicKeyToken=5660b08a1845a91e mono-devel=$toolchain"
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

bundle="$output/${bundles[0]}"
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
if ! grep -aFq -- 'map_digest' "$output/WebMap.dll"; then
    echo "privacy inspection failed: compiled map protocol missing" >&2
    exit 1
fi
echo "release privacy inspection passed"
