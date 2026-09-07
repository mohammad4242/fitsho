import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const trackedOpenApi = resolve(root, "contracts/openapi.json");
const trackedTypes = resolve(root, "packages/fitician-core/src/generated/api.ts");
const check = process.argv.includes("--check");
const temporaryRoot = resolve(root, ".codex-tmp/openapi-contract");
const openApiPath = check ? resolve(temporaryRoot, "openapi.json") : trackedOpenApi;
const typesPath = check ? resolve(temporaryRoot, "api.ts") : trackedTypes;

function run(command, args, cwd = root) {
  execFileSync(command, args, { cwd, stdio: "inherit" });
}

function generate() {
  mkdirSync(dirname(openApiPath), { recursive: true });
  mkdirSync(dirname(typesPath), { recursive: true });
  run(
    "uv",
    ["run", "python", "-m", "app.openapi_export", "--output", openApiPath],
    resolve(root, "backend"),
  );
  run("npm", [
    "exec",
    "--",
    "openapi-typescript",
    openApiPath,
    "--output",
    typesPath,
    "--export-type",
    "--alphabetize",
  ]);
}

function assertMatches(label, actualPath, expectedPath) {
  if (
    !existsSync(expectedPath) ||
    readFileSync(actualPath, "utf8") !== readFileSync(expectedPath, "utf8")
  ) {
    throw new Error(`${label} is out of date; run npm run generate:openapi`);
  }
}

try {
  if (check) {
    rmSync(temporaryRoot, { recursive: true, force: true });
    generate();
    assertMatches("contracts/openapi.json", openApiPath, trackedOpenApi);
    assertMatches("generated API types", typesPath, trackedTypes);
  } else {
    generate();
  }
} finally {
  if (check) {
    rmSync(temporaryRoot, { recursive: true, force: true });
  }
}
