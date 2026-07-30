# Changelog

## Unreleased

## 2.7.4 — 2026-07-30

### Security and privacy

- Remove public per-player records, positions, names, chat and message telemetry, and ping telemetry; the presence protocol now publishes an aggregate-only online count.
- Keep intentional public pins while replacing internal owner values with process-ephemeral aliases and JavaScript-safe IDs; validate private pin records and bound retained pins, owner mappings, coordinates, IDs, types, and text.
- Remove seed, internal world-name, open/public flag, server-info, and private endpoint/path metadata from public runtime and browser output.
- Apply no-store or immutable cache policy as appropriate, MIME-sniffing, referrer, frame, and same-origin Content Security Policy headers across normal, static, and error responses.
- Minimize the optional private quorum activity journal and link-claim records, set journal permissions before the first write, and keep activity/linking independent from downstream RSVP policy.

### Fixed

- Publish aggregate, fog, pin, and configuration snapshots from the main thread; bound WebSocket input, pin/browser work, webhook queues and timeouts, and identity churn.
- Require a content-addressed map digest, fixed-time digest comparison, one 16-lowercase-hex browser bundle, and cache-safe HTML/map behavior.
- Validate and clamp typed configuration values, keep test/debug independent, and exclude private server metadata from client configuration.
- Make webhook startup inert when disabled, keep enabled work bounded, avoid sensitive error details, and complete cancellation and teardown deterministically.
- Harden listener startup, HTTP failure handling, WebSocket reconnect/input behavior, Markdown image sources, and browser icon/timer cleanup.
- Replace the previously documented flat four-file compiler output, which was not installable because runtime serves `web/index.html`, with deterministic `dist/valheim-webmap-2.7.4.zip`. The archive has one top-level `WebMap/` plugin directory and a closed allowlist containing the two runtime DLLs, dependency notice, required static asset graph, and one content-addressed browser bundle.
- Replace the opaque vendored websocket binary with a signed .NET 3.5 source build from immutable upstream commit `4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1`; hash-lock and safely extract the source archive, pin the Mono/xbuild toolchain, compile WebMap against that output, and report each release artifact hash.

## 2.7.3 — 2026-07-28

### Added

- Server-owner `world_visibility_mode` policy with `fogged` (default), `hybrid`, and `full` browser-map rendering modes.
- Explicit release-output inclusion of `websocket-sharp.dll`.

### Fixed

- Generate a fingerprinted JavaScript bundle for every browser build and have the generated HTML reference it, preventing CDN clients from pairing new WebMap configuration with stale `main.js`.
- Serve the HTML entrypoint with `no-store` caching so browsers retrieve the current fingerprinted bundle reference.

## 2.7.2 — 2026-07-27

### Fixed

- Start the WebMap HTTP/WebSocket listener from the current Valheim dedicated-server world setup path.
- Guard listener startup for server mode, a ready world, and exactly-once execution.
- Update Unity image-conversion build compatibility for the tested current Valheim server assemblies.

### Verified

- Valheim Dedicated Server `l-0.221.12` / Steam build `21981590` / network version `36`.
- BepInExPack Valheim `5.4.2333` on Linux, crossplay enabled.
- HTTP map response and WebSocket upgrade from a separate LAN host.
