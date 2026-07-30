const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const output = path.resolve(root, process.argv[2] || "WebMap/bin/Release/net48");
const web = path.resolve(root, process.argv[3] || "WebMap/web");
const noticeSource = path.resolve(root, process.argv[4] || "THIRD-PARTY-NOTICES.txt");
const sourceBuiltDependency = path.resolve(process.argv[5] || "/tmp/websocket-sharp-build/websocket-sharp.dll");
const noticeName = "THIRD-PARTY-NOTICES.txt";
const fail = message => { throw new Error(`release packaging failed: ${message}`); };
const sha256 = file => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const sameFile = (left, right) => {
    if (!fs.existsSync(left) || !fs.existsSync(right)) return false;
    const leftData = fs.readFileSync(left);
    const rightData = fs.readFileSync(right);
    return leftData.length === rightData.length && crypto.timingSafeEqual(leftData, rightData);
};

if (!fs.statSync(output).isDirectory()) fail("release output is missing");
if (!fs.existsSync(sourceBuiltDependency) || !fs.statSync(sourceBuiltDependency).isFile() || fs.statSync(sourceBuiltDependency).size === 0) {
    fail("current source-built websocket-sharp.dll is missing or empty");
}
for (const dll of ["WebMap.dll", "websocket-sharp.dll"]) {
    const file = path.join(output, dll);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile() || fs.statSync(file).size === 0) {
        fail(`${dll} is missing or empty`);
    }
}
if (!sameFile(path.join(output, "websocket-sharp.dll"), sourceBuiltDependency)) {
    fail("source-built websocket-sharp.dll does not match the WebMap CopyLocal output");
}

const bundles = fs.readdirSync(web).filter(name => /^main\.[0-9a-f]{16}\.js$/.test(name));
if (bundles.length !== 1 || fs.existsSync(path.join(web, "main.js"))) {
    fail("expected one 16-lowercase-hex main bundle and no main.js");
}
if (!fs.existsSync(noticeSource) || !fs.statSync(noticeSource).isFile()) fail("third-party notice is missing");
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

const preserved = new Set(["WebMap.dll", "websocket-sharp.dll"]);
for (const entry of fs.readdirSync(output)) {
    if (!preserved.has(entry)) fs.rmSync(path.join(output, entry), {recursive: true, force: true});
}
fs.copyFileSync(path.join(web, bundles[0]), path.join(output, bundles[0]));
fs.copyFileSync(noticeSource, path.join(output, noticeName));

const expected = [noticeName, "WebMap.dll", bundles[0], "websocket-sharp.dll"].sort();
const actual = fs.readdirSync(output).sort();
if (actual.length !== 4 || actual.some((name, index) => name !== expected[index])) {
    fail("canonical package must contain exactly four allowed files");
}
for (const name of actual) {
    const stat = fs.statSync(path.join(output, name));
    if (!stat.isFile() || stat.size === 0) fail(`${name} is not a non-empty regular file`);
}
if (!sameFile(path.join(output, "websocket-sharp.dll"), sourceBuiltDependency)) {
    fail("source-built websocket-sharp.dll does not match the packaged dependency");
}

console.log(`canonical release package verified: ${actual.join(", ")}`);
console.log(`source-built websocket-sharp.dll SHA-256: ${sha256(sourceBuiltDependency)}`);
