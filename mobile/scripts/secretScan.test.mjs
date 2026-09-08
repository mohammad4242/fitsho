import assert from "node:assert/strict";
import test from "node:test";

import { findSecretMatches } from "./secret-scan.mjs";

test("secret scanner ignores empty and documented placeholder values", () => {
  const source = [
    "EXPO_PUBLIC_API_KEY=",
    "OPENCODE_ZEN_API_KEY=your-key",
    "client_secret: \"<configure-in-secret-store>\"",
  ].join("\n");

  assert.deepEqual(findSecretMatches(source), []);
});

test("secret scanner catches private keys without returning their contents", () => {
  const source = [
    "-----BEGIN " + "PRIVATE KEY-----",
    "not-a-real-key",
    "-----END " + "PRIVATE KEY-----",
  ].join("\n");

  const matches = findSecretMatches(source);

  assert.deepEqual(matches, [{ line: 1, rule: "private-key" }]);
  assert.doesNotMatch(JSON.stringify(matches), /not-a-real-key/u);
});

test("secret scanner catches committed provider credentials", () => {
  const awsKey = "AKIA" + "1234567890ABCDEF";
  const source = `${awsKey}\nAIza${"A".repeat(35)}\nsk-${"a".repeat(32)}`;

  assert.deepEqual(findSecretMatches(source), [
    { line: 1, rule: "aws-access-key" },
    { line: 2, rule: "google-api-key" },
    { line: 3, rule: "openai-compatible-key" },
  ]);
});

test("secret scanner catches non-placeholder quoted credentials", () => {
  const keyName = ["service", "secret"].join("_");
  const value = "production-credential-" + "x".repeat(24);
  const source = `${keyName}: "${value}"`;

  assert.deepEqual(findSecretMatches(source), [{ line: 1, rule: "quoted-secret" }]);
});
