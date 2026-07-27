# Changelog

## 2.7.2 — 2026-07-27

### Fixed

- Start the WebMap HTTP/WebSocket listener from the current Valheim dedicated-server world setup path.
- Guard listener startup for server mode, a ready world, and exactly-once execution.
- Update Unity image-conversion build compatibility for the tested current Valheim server assemblies.

### Verified

- Valheim Dedicated Server `l-0.221.12` / Steam build `21981590` / network version `36`.
- BepInExPack Valheim `5.4.2333` on Linux, crossplay enabled.
- HTTP map response and WebSocket upgrade from a separate LAN host.
