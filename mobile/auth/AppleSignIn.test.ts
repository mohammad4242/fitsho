import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("uses the native iOS Apple authentication flow and a request nonce", async () => {
  const source = await readFile(resolve(import.meta.dirname, "AppleSignIn.tsx"), "utf8");

  expect(source).toMatch(/Platform\.OS\s*===\s*["']ios["']/u);
  expect(source).toMatch(/isAvailableAsync/);
  expect(source).toMatch(/signInAsync/);
  expect(source).toMatch(/nonce/);
  expect(source).toMatch(/requestedScopes/);
});
