# Valheim WebMap

A **server-side** Valheim dedicated-server mod that publishes a browser map without exposing a viewer-facing player roster or per-player telemetry. Players use unmodded clients; no client mod is required.

The public WebMap contains terrain and fog according to the server owner's visibility policy, an aggregate online count, and intentional map pins. Pins deliberately disclose their coordinates and text, together with process-ephemeral owner aliases and JavaScript-safe numeric IDs. Those aliases are convenience labels for one server process, **not durable anonymity** and not a promise that pin text or coordinates cannot identify their author.

> [!IMPORTANT]
> **Current-Valheim compatibility baseline:** WebMap **v2.7.4** targets **Valheim Dedicated Server `l-0.221.12`** (Steam build **`21981590`**, network version **36**) on Linux with BepInExPack Valheim **5.4.2333** and a crossplay-enabled AMP instance. The underlying runtime path was tested successfully on **2026-07-27**; the v2.7.4 security, privacy, and packaging candidate is CI-verified but has not been deployed. Validate newer Valheim builds before production rollout.

## Features

- Explorable terrain map in a desktop or mobile browser.
- Owner-controlled `fogged`, `hybrid`, and `full` terrain/fog visibility policy.
- Aggregate online count with no connected-player roster or per-player records.
- Intentional shared map pins with bounded coordinates and text, process-ephemeral aliases, and JavaScript-safe IDs.
- Pin creation and removal through in-game commands.
- Optional Discord status webhook and private quorum integration; neither expands the public viewer protocol.

The viewer protocol does **not** publish positions, pings, chat/messages, a roster, player names, health, PvP, bed, or death state. It also excludes the world seed, internal world name, server open/public flags, and private endpoints or filesystem locations.

![WebMap screenshot](screenshot.webp)

## Compatibility and release status

| Component | Validated target |
|---|---|
| WebMap source candidate | `2.7.4` |
| Valheim Dedicated Server | `l-0.221.12` |
| Steam dedicated-server build | `21981590` |
| Valheim network version | `36` |
| Loader | BepInExPack Valheim `5.4.2333` |
| Server mode | Linux dedicated server, crossplay enabled |

The v2.7.4 source candidate retains guarded current-Valheim world-setup startup, content-addressed map and browser assets, bounded configuration, hardened HTTP responses, and deterministic teardown. No tag or release is implied by source metadata alone.

## Installation

1. Install a Valheim-compatible BepInEx loader. For the validated AMP baseline, use BepInExPack Valheim and preserve the host's Doorstop/environment configuration.
2. Obtain the canonical v2.7.4 release payload. It contains exactly four files:
   - `WebMap.dll`
   - `websocket-sharp.dll`
   - one `main.<16 lowercase hex>.js`
   - `THIRD-PARTY-NOTICES.txt`
3. Stop the dedicated server. Copy the complete payload into its WebMap plugin installation, preserving the hashed JavaScript filename and bundled notice. Do not copy PDBs, configuration files, saved map data, or additional DLLs from a build workspace.
4. Start the server once so it creates operator configuration, then stop it before editing settings. Runtime edits can be overwritten during shutdown.
5. Restrict the raw listener to a trusted network. For any public exposure, use an **HTTPS reverse proxy** that forwards normal HTTP and WebSocket upgrades. Do not expose the raw listener directly to the Internet.

See [reverse-proxy guidance](docs/REVERSE_PROXY.md) for an example that does not disclose deployment-specific addresses.

### Multiple server instances on one host

Every running Valheim/WebMap instance must use a distinct `server_port`. The default is `3000`. Configure a different valid port per instance, and point the reverse proxy at the intended backend. Never publish private backend addresses in documentation or support logs.

### Map visibility policy

The owner selects one of these browser-map policies:

- `fogged` — default; explored areas are visible and unexplored terrain remains covered.
- `hybrid` — retains exploration fog while showing generated terrain faintly underneath.
- `full` — shows the full generated terrain map without the fog overlay.

This is an owner policy, not a viewer preference. It controls terrain/fog visibility only; it does not enable per-player telemetry.

### Optional private quorum activity and linking

The private quorum activity journal is disabled by default. When an operator explicitly enables it, join/leave activity and private link-claim events are appended for a separately operated integration. Link-claim material is minimized before storage. These records are not served by WebMap and must remain access-controlled; examples intentionally omit identifiers, digests, and deployment paths.

Activity collection, account linking, and RSVP eligibility are separate concerns. **Activity and linking do not select an RSVP presence policy**: a downstream operator must define eligibility independently, and this project does not choose between an any-presence rule and a duration threshold.

## Updating

1. Stop the dedicated server and back up operator configuration and map state outside the replacement directory.
2. Verify the new release contains exactly the four files listed above. Verify `websocket-sharp.dll` against [dependency provenance](docs/DEPENDENCY_PROVENANCE.md), and retain the notice unchanged.
3. Remove the previous release payload, then install the complete replacement. Do not preserve an unhashed `main.js`, stale hashed bundles, PDBs, extra DLLs, generated configuration, or private data in the release directory.
4. Restart the dedicated server and confirm startup through the ordinary BepInEx log without publishing private endpoints or paths.
5. Confirm the HTTPS entrypoint and WebSocket upgrade through the reverse proxy. A hard refresh should retrieve the current content-addressed bundle.

## Pin commands

Press `Enter` to open Valheim chat. Commands are not case-sensitive.

- `!pin` — place a dot pin at the current position.
- `!pin my pin name` — place a named dot pin.
- `!pin [pin-type] [text]` — create a `dot`, `fire`, `mine`, `house`, or `cave` pin.
- `!undoPin` — delete the caller's most recent pin.
- `!deletePin [text]` — delete the caller's most recent exact-text match.

Pins are intentional public map content. Avoid entering personal information or sensitive locations in pin text. The server bounds coordinates, text, retained records, and per-owner pin count.

## Security and privacy

WebMap follows an **aggregate-only privacy model** for presence: a reachable viewer receives only the total online count, never one record per connected player. The service does not expose names, positions, pings, messages, health/PvP/bed/death state, the seed, internal world label, open/public flags, or private integration routes and storage locations.

The map itself is still sensitive. Owner-selected terrain/fog policy may reveal geography or exploration, and intentional map pins reveal coordinates and text. Process-ephemeral aliases reduce direct reuse of internal owner keys, but they do not make sensitive pin content anonymous. Treat public exposure as deliberate publication: terminate TLS at an HTTPS reverse proxy, apply authentication or network restrictions appropriate to the community, forward WebSocket upgrades explicitly, and keep the backend listener private.

The optional journal and link-claim flow are private operator integrations, not part of the browser API. Protect their storage and consumers separately from WebMap's public surface.

## Dependency provenance and licences

The release includes a pinned `websocket-sharp.dll` and `THIRD-PARTY-NOTICES.txt`. Exact measured dependency facts and the unresolved source-build provenance are documented in [docs/DEPENDENCY_PROVENANCE.md](docs/DEPENDENCY_PROVENANCE.md).

- Current fork maintenance: [dogekamii](https://github.com/dogekamii)
- Upstream maintenance: [Jeff Clark / h0tw1r3](https://github.com/h0tw1r3)
- Original work: [Kyle Paulsen](https://github.com/kylepaulsen)
- Background by [webtreats], released under [CC BY 2.0].

[webtreats]: https://www.flickr.com/photos/webtreatsetc/4081217254
[CC BY 2.0]: https://creativecommons.org/licenses/by/2.0/
