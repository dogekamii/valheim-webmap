"""Regression contract for browser bundle cache invalidation.

A deployment must not serve a newly configured WebMap backend with an older
cached browser bundle.  The release build emits a content-addressed main
bundle and the generated document references that exact file.  The HTML
entrypoint is never cacheable because it selects the current bundle URL.
"""
from pathlib import Path
import re

repo = Path(__file__).parents[1]
web = repo / "WebMap" / "web"
cache_patch = (repo / "WebMap" / "Patches" / "FrontendCacheHeadersPatch.cs").read_text()
index = (web / "index.html").read_text()

assert '[HarmonyPatch(typeof(MapDataServer), "ServeStaticFiles")]' in cache_patch
assert 'rawRequestPath != "/" && rawRequestPath != "/index.html"' in cache_patch
assert 'HttpResponseHeader.CacheControl, "no-store"' in cache_patch

match = re.search(r'<script src="(main\.[0-9a-f]+\.js)"></script>', index)
assert match, "index.html must reference a content-addressed main bundle"
assert (web / match.group(1)).is_file(), "the referenced content-addressed bundle must exist"
assert not (web / "main.js").exists(), "the fixed main.js URL must not be emitted"
