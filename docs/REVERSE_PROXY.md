# Reverse-proxy deployment

WebMap runs inside the Valheim dedicated-server process. A separate reverse-proxy container is optional, but recommended for HTTPS publication and for keeping the raw WebMap listener off public networks.

## Required proxy behavior

Proxy HTTP and WebSocket traffic to the WebMap backend. A proxy must preserve upgrade headers and use long read/send timeouts for the live socket.

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
proxy_read_timeout 3600;
proxy_send_timeout 3600;
proxy_buffering off;
```

## Multiple Valheim servers on one game host

The WebMap listener belongs to each Valheim process, not to the proxy. Configure a unique WebMap port per instance:

| Environment | WebMap backend example | Proxy frontend example |
|---|---:|---:|
| Production Valheim | `10.0.1.10:3000` | dedicated proxy IP, TCP `80` |
| Development Valheim | `10.0.1.10:3001` | separate dedicated proxy IP, TCP `80` |

Use a reverse proxy to terminate TLS and enforce access control. Do not publish either raw backend port to the WAN.
