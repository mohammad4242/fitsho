import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";

const root = new URL("..", import.meta.url);

test("OpenAPI generation is reproducible", () => {
  const result = spawnSync(process.execPath, ["scripts/generate-openapi.mjs", "--check"], {
    cwd: root,
    encoding: "utf8",
  });

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const generatedTypes = readFileSync(
    new URL("../packages/fitician-core/src/generated/api.ts", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(generatedTypes, /\bany\b/);
});
