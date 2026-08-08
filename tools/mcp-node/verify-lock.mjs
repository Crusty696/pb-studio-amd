import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const minimumNode = [20, 18, 1];
const runtimeValidation = process.argv.includes("--runtime");
const lockArgument = process.argv.slice(2).find(argument => argument !== "--runtime");

const expected = {
  lockSha256: "2D542EE2E1F30793777E23959842325D032D75FB7E521314D4AA1EE23AFE5152",
  lockfileVersion: 3,
  packageNodes: 110,
  context7Version: "3.2.5",
  context7Integrity: "sha512-m+GIwQKBx2yCnLN7Et3wqkuTk1iPkMySQH2i6KiUf4B9wVI0tgtjeXRcDfFZPf5rnRA3gjYhr1FqQqMb9aSRnw==",
  cavemanVersion: "0.1.0",
  cavemanIntegrity: "sha512-AH81oXnhBTRrqbolhq3vTMrJxP+Zgk5cTxMYatMVNGNALqqdviY+3sTkSxynCfZQfxNXUwAwi5mWSlrXxM4TkA==",
};

const toolDir = path.dirname(fileURLToPath(import.meta.url));
const lockPath = path.resolve(lockArgument ?? path.join(toolDir, "package-lock.json"));
const lockBytes = fs.readFileSync(lockPath);
const lock = JSON.parse(lockBytes.toString("utf8"));
const failures = [];
const root = lock.packages?.[""];
const context7 = lock.packages?.["node_modules/@upstash/context7-mcp"];
const caveman = lock.packages?.["node_modules/caveman-shrink"];
const packageNodes = Object.entries(lock.packages ?? {}).filter(([entryPath]) => entryPath.startsWith("node_modules/"));

function requireEqual(label, actual, wanted) {
  if (actual !== wanted) failures.push(`${label}: expected ${wanted}, got ${actual}`);
}

const nodeVersion = process.versions.node.split(".").map(Number);
const nodeSupported = nodeVersion[0] > minimumNode[0] ||
  (nodeVersion[0] === minimumNode[0] && nodeVersion[1] > minimumNode[1]) ||
  (nodeVersion[0] === minimumNode[0] && nodeVersion[1] === minimumNode[1] && nodeVersion[2] >= minimumNode[2]);
if (!nodeSupported) failures.push(`Node.js ${minimumNode.join(".")} or newer required; got ${process.versions.node}`);

requireEqual("lock SHA-256", crypto.createHash("sha256").update(lockBytes).digest("hex").toUpperCase(), expected.lockSha256);
requireEqual("lockfileVersion", lock.lockfileVersion, expected.lockfileVersion);
requireEqual("package node count", packageNodes.length, expected.packageNodes);
requireEqual("root Context7 version", root?.dependencies?.["@upstash/context7-mcp"], expected.context7Version);
requireEqual("locked Context7 version", context7?.version, expected.context7Version);
requireEqual("Context7 integrity", context7?.integrity, expected.context7Integrity);
requireEqual("root caveman-shrink version", root?.dependencies?.["caveman-shrink"], expected.cavemanVersion);
requireEqual("locked caveman-shrink version", caveman?.version, expected.cavemanVersion);
requireEqual("caveman-shrink integrity", caveman?.integrity, expected.cavemanIntegrity);
requireEqual("root Node engine", root?.engines?.node, ">=20.18.1");

for (const [entryPath, entry] of packageNodes) {
  if (entry.resolved && !entry.integrity) failures.push(`${entryPath}: resolved entry has no integrity`);
}

if (runtimeValidation && failures.length === 0) {
  for (const [entryPath, entry] of packageNodes) {
    const installedManifestPath = path.join(toolDir, entryPath, "package.json");
    if (!fs.existsSync(installedManifestPath)) {
      failures.push(`${entryPath}: installed package is missing`);
      continue;
    }
    try {
      const installedManifest = JSON.parse(fs.readFileSync(installedManifestPath, "utf8"));
      requireEqual(`${entryPath} installed version`, installedManifest.version, entry.version);
    } catch (error) {
      failures.push(`${entryPath}: installed package manifest is invalid: ${error.message}`);
    }
  }
}

if (runtimeValidation && failures.length === 0) {
  const npmArguments = ["ls", "--all", "--offline", "--ignore-scripts", "--json"];
  const command = process.platform === "win32" ? (process.env.ComSpec || "cmd.exe") : "npm";
  const commandArguments = process.platform === "win32"
    ? ["/d", "/s", "/c", `npm ${npmArguments.join(" ")}`]
    : npmArguments;
  const treeCheck = spawnSync(command, commandArguments, {
    cwd: toolDir,
    encoding: "utf8",
    env: {
      ...process.env,
      npm_config_offline: "true",
      npm_config_ignore_scripts: "true",
    },
    maxBuffer: 4 * 1024 * 1024,
    timeout: 15_000,
    windowsHide: true,
  });
  if (treeCheck.error) failures.push(`installed tree validation failed: ${treeCheck.error.message}`);
  else if (treeCheck.status !== 0) failures.push(`installed tree validation exited ${treeCheck.status}: ${treeCheck.stderr.trim()}`);
}

if (failures.length) {
  for (const failure of failures) console.error(failure);
  process.exit(1);
}

console.log(`verified lockfile v${lock.lockfileVersion}, ${packageNodes.length} package nodes`);
