const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const mode = process.argv[2] || "production";
const root = path.resolve(__dirname, "..");
const webDirectory = path.join(root, "WebMap", "web");
const entryPoint = path.join(root, "WebMap", "web-src", "index.js");
const bundlePath = path.join(webDirectory, "main.js");
const indexPath = path.join(webDirectory, "index.html");

for (const file of fs.readdirSync(webDirectory)) {
    if (/^main(?:\.[0-9a-f]+)?\.js$/.test(file)) {
        fs.unlinkSync(path.join(webDirectory, file));
    }
}

const webpack = require.resolve("webpack/bin/webpack.js");
const result = spawnSync(process.execPath, [webpack, entryPoint, "-o", webDirectory, "--mode", mode], {
    cwd: root,
    stdio: "inherit"
});

if (result.status !== 0) {
    process.exit(result.status || 1);
}

const digest = crypto.createHash("sha256").update(fs.readFileSync(bundlePath)).digest("hex").slice(0, 16);
const bundleName = `main.${digest}.js`;
fs.renameSync(bundlePath, path.join(webDirectory, bundleName));

const index = fs.readFileSync(indexPath, "utf8");
const updatedIndex = index.replace(
    /<script src="main(?:\.[0-9a-f]+)?\.js"><\/script>/,
    `<script src="${bundleName}"></script>`
);

if (updatedIndex === index) {
    throw new Error("WebMap index.html does not contain a replaceable main bundle script tag");
}

fs.writeFileSync(indexPath, updatedIndex);
