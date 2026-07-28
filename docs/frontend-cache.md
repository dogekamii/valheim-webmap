# Frontend cache and release contract

WebMap's release build emits the browser application as a content-addressed
file named `WebMap/web/main.<sha256-prefix>.js`.  During the same build it
rewrites `WebMap/web/index.html` to reference that exact filename and removes
older generated `main.*.js` bundles.

The WebMap HTTP server marks `index.html` as `Cache-Control: no-store`; do not
override that policy in a reverse proxy or CDN.  The HTML entrypoint selects
the release's current JavaScript URL, while the hashed JavaScript file can be
cached immutably.  This prevents a CDN from combining a new `/config` response
with a JavaScript bundle from a previous WebMap release.

## Release and CDN procedure

1. Build releases through `./build.sh --configuration Release` (or the
   repository release-build CI job).  Do not copy a `web-src` directory or an
   unbuilt checkout into the plugin directory.
2. Deploy the full WebMap plugin directory and restart the server.
3. Preserve origin cache-control headers.  If a CDN has cached an older release
   before this contract is deployed, use a scoped purge for the map root,
   `index.html`, and legacy `main.js` URL once; do not perform a zone-wide
   purge.
4. Verify the HTML's `main.<hash>.js` URL is different from the prior release
   and returns the frontend code expected by the deployed `/config` endpoint.
