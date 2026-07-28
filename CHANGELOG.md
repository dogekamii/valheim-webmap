# Changelog

## Unreleased

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
