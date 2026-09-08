import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

test("CI covers every Phase 14 release gate", async () => {
  const workflow = await readFile(resolve(root, ".github/workflows/ci.yml"), "utf8");
  for (const requiredCheck of [
    "uv run pytest",
    "npm run test --workspace frontend",
    "npm run lint --workspace frontend",
    "npm run build --workspace frontend",
    "npm run test:core",
    "npm run test --workspace @fitician/mobile",
    "npm run test:native --workspace @fitician/mobile",
    "npm run test:mobile:foundation",
    "npm run typecheck:mobile",
    "npm run validate:mobile",
    "npm run check:openapi",
    "npm run test:contracts",
    "npm run prebuild",
    ":app:assembleDebug",
    "audit:dependencies",
    "security:secrets",
  ]) {
    assert.match(workflow, new RegExp(requiredCheck.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&")), requiredCheck);
  }
});

test("CI uses read-only permissions and a clean dependency install", async () => {
  const workflow = await readFile(resolve(root, ".github/workflows/ci.yml"), "utf8");
  assert.match(workflow, /permissions:\s*\n\s*contents:\s*read/u);
  assert.match(workflow, /npm ci/u);
});

test("CI invokes the frontend workspace by its real package name", async () => {
  const workflow = await readFile(resolve(root, ".github/workflows/ci.yml"), "utf8");
  const frontendPackage = JSON.parse(
    await readFile(resolve(root, "frontend/package.json"), "utf8"),
  );

  assert.equal(frontendPackage.name, "frontend");
  assert.match(workflow, /npm run test --workspace frontend/u);
  assert.match(workflow, /npm run lint --workspace frontend/u);
  assert.match(workflow, /npm run build --workspace frontend/u);
  assert.doesNotMatch(workflow, /--workspace @fitician\/frontend/u);
});

test("CI keeps the backend lockfile tracked for frozen installs", async () => {
  const workflow = await readFile(resolve(root, ".github/workflows/ci.yml"), "utf8");
  const trackedFiles = execFileSync(
    "git",
    ["ls-files", "--error-unmatch", "backend/uv.lock"],
    { cwd: root, encoding: "utf8" },
  );

  assert.match(trackedFiles, /^backend\/uv\.lock\s*$/u);
  assert.match(workflow, /cache-dependency-glob:\s*backend\/uv\.lock/u);
  assert.match(workflow, /uv sync --frozen --extra dev/u);
});
