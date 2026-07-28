# Valheim WebMap

A **server-side** Valheim dedicated-server mod that publishes a live browser map with player positions, exploration, pings, and shared pins. Players use unmodded clients — no client mod is required.

> [!IMPORTANT]
> **Current-Valheim compatibility:** WebMap **v2.7.3** was tested successfully on **2026-07-27** with **Valheim Dedicated Server `l-0.221.12`** (Steam build **`21981590`**, network version **36**) on Linux, using BepInExPack Valheim **5.4.2333** and a crossplay-enabled AMP instance. This compatibility statement applies to that exact tested server build; newer Valheim builds should be validated before production rollout.

## Features

- Explorable world map in a desktop or mobile browser.
- Live player positions for players who enable **Visible to other players** in Valheim's in-game map settings.
- In-game pings shown on the browser map.
- Player-created shared pins via in-game chat commands.
- Connected-player list, auto-follow, and connect/chat messages.
- Optional Discord server-status and player join/leave notifications.

![WebMap screenshot](screenshot.webp)

## Compatibility and release status

| Component | Tested value |
|---|---|
| WebMap | `2.7.3` |
| Valheim Dedicated Server | `l-0.221.12` |
| Steam dedicated-server build | `21981590` |
| Valheim network version | `36` |
| Loader | BepInExPack Valheim `5.4.2333` |
| Server mode | Linux dedicated server, crossplay enabled |

The v2.7.3 release retains the guarded current-Valheim world-setup listener startup, adds owner-controlled `fogged`, `hybrid`, and `full` map visibility, and keeps browser clients cache-fresh through fingerprinted JavaScript bundles with a no-store HTML entrypoint.

## Installation

1. Install a Valheim-compatible BepInEx loader. For current AMP Valheim templates, use **BepInExPack Valheim** and preserve AMP's Doorstop/environment configuration.
2. Copy the release `WebMap` directory into the dedicated server's plugin directory:

   ```text
   <Valheim dedicated server>/BepInEx/plugins/WebMap
   ```

3. Start the server once. WebMap creates its configuration file at:

   ```text
   <Valheim dedicated server>/BepInEx/config/com.github.h0tw1r3.valheim.webmap.cfg
   ```

4. Stop the server before changing configuration. Edit the file, then start the server again. Configuration changes made while the server runs can be overwritten on shutdown.
5. By default, browse to `http://<server-ip>:3000` from a permitted network. For public access, put WebMap behind an HTTPS reverse proxy; do **not** expose the raw listener directly to the Internet.

### Multiple server instances on one host

Every running Valheim/WebMap instance must use a distinct `server_port`. Set this under the `[Server]` section of its generated configuration file:

```ini
[Server]
server_port = 3001
```

The default is `3000`. A reverse proxy should pass both ordinary HTTP traffic and WebSocket upgrades to the selected backend port.

### Map visibility policy

The server owner controls browser-map visibility with this generated configuration value:

```ini
[World]
## Controls the browser map fog. Valid values are fogged, hybrid, and full.
world_visibility_mode = fogged
```

- `fogged` — **default** and legacy behavior: explored areas are visible and all other areas remain fogged.
- `hybrid` — keeps the exploration fog, while showing the server-generated terrain map faintly underneath it.
- `full` — hides the fog overlay and shows the full generated map.

This policy is sent by the server in its configuration response and is not exposed as a viewer preference or UI toggle. Restart WebMap after changing it.

## Updating

1. Back up the server's `BepInEx/plugins/WebMap` directory and any map data before replacing files.
2. Replace the plugin directory with the new release payload.
3. Restart the dedicated server and confirm the WebMap listener is present in `BepInEx/LogOutput.log`.
4. If the UI appears stale, hard-refresh or clear the browser cache.

## Chat commands

Press `Enter` to open Valheim chat. Commands are not case-sensitive.

- `!pin` — place a dot pin at your current position.
- `!pin my pin name` — place a named dot pin.
- `!pin [pin-type] [text]` — create `dot`, `fire`, `mine`, `house`, or `cave` pins. Example: `!pin house my awesome base`
- `!undoPin` — delete your most recent pin.
- `!deletePin [text]` — delete the most recent pin whose text matches exactly.

The server configuration controls the maximum number of pins per player; older pins are removed if the limit is exceeded.

## Security

A WebMap instance exposes player positions, exploration state, and shared pins to anyone who can reach it. Restrict network reachability deliberately and use reverse-proxy authentication and HTTPS before public publication.

## Licence and credit

Where applicable, assume content is under the MIT licence.

- Current fork maintenance: [dogekamii](https://github.com/dogekamii)
- Upstream maintenance: [Jeff Clark / h0tw1r3](https://github.com/h0tw1r3)
- Original work: [Kyle Paulsen](https://github.com/kylepaulsen)
- Background by [webtreats], released under [CC BY 2.0].

[webtreats]: https://www.flickr.com/photos/webtreatsetc/4081217254
[CC BY 2.0]: https://creativecommons.org/licenses/by/2.0/
