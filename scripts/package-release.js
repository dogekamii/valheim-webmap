const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const root = path.resolve(__dirname, "..");
const compilerOutput = path.resolve(root, process.argv[2] || "WebMap/bin/Release/net48");
const web = path.resolve(root, process.argv[3] || "WebMap/web");
const noticeSource = path.resolve(root, process.argv[4] || "THIRD-PARTY-NOTICES.txt");
const sourceBuiltDependency = path.resolve(process.argv[5] || "/tmp/websocket-sharp-build/websocket-sharp.dll");
const canonicalArchive = "dist/valheim-webmap-2.7.4.zip";
const dist = path.resolve(root, process.argv[6] || path.dirname(canonicalArchive));
const archivePath = path.join(dist, path.basename(canonicalArchive));
const stagingRoot = path.join(dist, ".staging");
const pluginRoot = path.join(stagingRoot, "WebMap");
const pluginWeb = path.join(pluginRoot, "web");
const noticeName = "THIRD-PARTY-NOTICES.txt";
const nonGeneratedWebFiles = ["index.html", "style.css", "mapIcons.png", "tile.webp"];
const fail = message => { throw new Error(`release packaging failed: ${message}`); };
const regularNonEmpty = file => {
    if (!fs.existsSync(file)) return false;
    const stat = fs.lstatSync(file);
    return stat.isFile() && !stat.isSymbolicLink() && stat.size > 0;
};
const sameFile = (left, right) => {
    if (!regularNonEmpty(left) || !regularNonEmpty(right)) return false;
    const leftData = fs.readFileSync(left);
    const rightData = fs.readFileSync(right);
    return leftData.length === rightData.length && crypto.timingSafeEqual(leftData, rightData);
};

if (!fs.existsSync(compilerOutput) || !fs.statSync(compilerOutput).isDirectory()) fail("compiler staging output is missing");
for (const dll of ["WebMap.dll", "websocket-sharp.dll"]) {
    if (!regularNonEmpty(path.join(compilerOutput, dll))) fail(`${dll} is missing or empty in compiler staging output`);
}
if (!sameFile(path.join(compilerOutput, "websocket-sharp.dll"), sourceBuiltDependency)) {
    fail("source-built websocket-sharp.dll does not match the WebMap CopyLocal output");
}

const bundles = fs.readdirSync(web).filter(name => /^main\.[0-9a-f]{16}\.js$/.test(name));
if (bundles.length !== 1 || fs.existsSync(path.join(web, "main.js"))) {
    fail("expected one 16-lowercase-hex main bundle and no main.js");
}
const bundle = bundles[0];
if (!regularNonEmpty(path.join(web, bundle))) fail("generated main bundle is empty or not a regular file");
for (const name of nonGeneratedWebFiles) {
    if (!regularNonEmpty(path.join(web, name))) fail(`required static file ${name} is missing or empty`);
}
const index = fs.readFileSync(path.join(web, "index.html"), "utf8");
if (!index.includes(`<script src="${bundle}"></script>`) || /<script\s+src=["']main\.js["']/.test(index)) {
    fail("index.html does not reference exactly the generated hashed bundle");
}
if (!regularNonEmpty(noticeSource)) fail("third-party notice is missing");
const notice = fs.readFileSync(noticeSource, "utf8");
for (const required of [
    "https://github.com/sta/websocket-sharp",
    "4cbd1e0ccdbf9f5cb322a7c14e3c84e19db5dee1",
    "310267b8fe24ab69e95c78425e24a3644cf4490693c7c398b280d020b435e43a",
    "Permission is hereby granted, free of charge",
    "THE SOFTWARE IS PROVIDED \"AS IS\"",
    "built from",
]) {
    if (!notice.includes(required)) fail("third-party notice is incomplete");
}
if (/unverified/i.test(notice)) fail("third-party notice retains unresolved binary provenance wording");

fs.rmSync(stagingRoot, { recursive: true, force: true });
fs.rmSync(archivePath, { force: true });
fs.mkdirSync(pluginWeb, { recursive: true });
fs.copyFileSync(path.join(compilerOutput, "WebMap.dll"), path.join(pluginRoot, "WebMap.dll"));
fs.copyFileSync(path.join(compilerOutput, "websocket-sharp.dll"), path.join(pluginRoot, "websocket-sharp.dll"));
fs.copyFileSync(noticeSource, path.join(pluginRoot, noticeName));
for (const name of [...nonGeneratedWebFiles, bundle]) {
    fs.copyFileSync(path.join(web, name), path.join(pluginWeb, name));
}

const archiveMembers = [
    "WebMap/WebMap.dll",
    "WebMap/websocket-sharp.dll",
    "WebMap/THIRD-PARTY-NOTICES.txt",
    "WebMap/web/index.html",
    "WebMap/web/style.css",
    "WebMap/web/mapIcons.png",
    "WebMap/web/tile.webp",
    `WebMap/web/${bundle}`,
];
const writer = path.join(root, "scripts", "create-release-archive.py");
const result = spawnSync("python3", [writer, stagingRoot, archivePath, ...archiveMembers], {
    cwd: root,
    stdio: "inherit",
});
if (result.status !== 0) fail("deterministic archive creation failed");
if (!regularNonEmpty(archivePath)) fail("installable release archive is missing or empty");
if (!sameFile(path.join(pluginRoot, "websocket-sharp.dll"), sourceBuiltDependency)) {
    fail("source-built websocket-sharp.dll does not match the staged install dependency");
}
console.log(`canonical installable release archive created: ${path.relative(root, archivePath)}`);
