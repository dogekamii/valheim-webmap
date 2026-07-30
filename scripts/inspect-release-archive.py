#!/usr/bin/env python3
"""Inspect the actual installable WebMap archive as a closed runtime boundary."""
from argparse import ArgumentParser
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ARCHIVE_NAME = "valheim-webmap-2.7.4.zip"
STATIC_MEMBERS = {
    "WebMap/WebMap.dll",
    "WebMap/websocket-sharp.dll",
    "WebMap/THIRD-PARTY-NOTICES.txt",
    "WebMap/web/index.html",
    "WebMap/web/style.css",
    "WebMap/web/mapIcons.png",
    "WebMap/web/tile.webp",
}
BUNDLE_PATTERN = re.compile(r"^WebMap/web/main\.([0-9a-f]{16})\.js$")
NOTICE_REQUIREMENTS = (
    "https://github.com/sta/websocket-sharp",
    "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1",
    "310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a",
    "Permission is hereby granted, free of charge",
    'THE SOFTWARE IS PROVIDED "AS IS"',
    "built from",
)


def fail(message: str) -> None:
    raise SystemExit(f"release archive inspection failed: {message}")


class IndexGraph(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "link" and "stylesheet" in values.get("rel", "").split() and values.get("href"):
            self.styles.append(values["href"])


parser = ArgumentParser()
parser.add_argument("archive")
parser.add_argument("--source-built")
parser.add_argument("--compiler-output")
args = parser.parse_args()
archive_path = Path(args.archive)
if archive_path.name != ARCHIVE_NAME or not archive_path.is_file() or archive_path.is_symlink() or archive_path.stat().st_size == 0:
    fail("canonical archive name/path is missing, empty, or not a regular file")

with zipfile.ZipFile(archive_path, "r") as archive:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        fail("duplicate archive member")
    for info in infos:
        name = info.filename
        member = PurePosixPath(name)
        if "\\" in name or member.is_absolute() or ".." in member.parts or not member.parts or member.parts[0] != "WebMap":
            fail("absolute, traversal, or non-WebMap archive path")
        mode = info.external_attr >> 16
        if info.is_dir() or (mode and not stat.S_ISREG(mode)):
            fail("directories, links, devices, and other non-regular members are forbidden")
        if info.flag_bits & 0x1:
            fail("encrypted archive members are forbidden")
        if info.file_size == 0:
            fail(f"empty archive member: {name}")
    bundles = [name for name in names if BUNDLE_PATTERN.fullmatch(name)]
    if len(bundles) != 1:
        fail("expected exactly one main.<16 lowercase hex>.js")
    bundle = bundles[0]
    expected = STATIC_MEMBERS | {bundle}
    if set(names) != expected or len(names) != len(expected):
        fail("archive member allowlist mismatch")
    if len([name for name in names if name.lower().endswith(".dll")]) != 2:
        fail("archive must contain exactly two runtime DLLs")
    contents = {name: archive.read(name) for name in names}

bundle_hash = sha256(contents[bundle]).hexdigest()
if BUNDLE_PATTERN.fullmatch(bundle).group(1) != bundle_hash[:16]:
    fail("bundle filename does not match its SHA-256 content prefix")
index = contents["WebMap/web/index.html"].decode("utf-8")
graph = IndexGraph()
graph.feed(index)
bundle_name = PurePosixPath(bundle).name
if graph.scripts != [bundle_name] or graph.styles != ["style.css"] or "main.js" in index:
    fail("index.html does not reference exactly the packaged hashed bundle and stylesheet")
css = contents["WebMap/web/style.css"].decode("utf-8")
css_assets = {
    match.strip().strip('"\'')
    for match in re.findall(r"url\(\s*([^\)]+?)\s*\)", css)
    if not match.strip().strip('"\'').startswith("data:")
}
if css_assets != {"tile.webp", "mapIcons.png"}:
    fail("stylesheet asset graph does not match the packaged images")
notice = contents["WebMap/THIRD-PARTY-NOTICES.txt"].decode("utf-8")
if any(required not in notice for required in NOTICE_REQUIREMENTS) or re.search(r"unverified|unresolved", notice, re.I):
    fail("third-party notice is incomplete or stale")

websocket_bytes = contents["WebMap/websocket-sharp.dll"]
if args.source_built:
    source = Path(args.source_built)
    if not source.is_file() or source.is_symlink() or source.read_bytes() != websocket_bytes:
        fail("archive websocket-sharp.dll is not the current source-built output")
if args.compiler_output:
    compiler = Path(args.compiler_output) / "websocket-sharp.dll"
    if not compiler.is_file() or compiler.is_symlink() or compiler.read_bytes() != websocket_bytes:
        fail("archive websocket-sharp.dll does not match compiler staging output")

archive_bytes = archive_path.read_bytes()
archive_hash = sha256(archive_bytes).hexdigest()
members = ",".join(sorted(names))
print(f"installable release archive verified: name={archive_path.name} sha256={archive_hash} size={len(archive_bytes)} members={members}")
print(f"::notice file=scripts/inspect-release-archive.py,line=1::release archive name={archive_path.name} sha256={archive_hash} size={len(archive_bytes)} members={members}")
