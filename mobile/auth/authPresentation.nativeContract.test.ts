import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps auth screens on the native premium scaffold", async () => {
  const scaffold = await readFile(resolve(import.meta.dirname, "AuthScaffold.tsx"), "utf8");
  const signIn = await readFile(resolve(import.meta.dirname, "../app/(auth)/auth/sign-in.tsx"), "utf8");

  expect(scaffold).toMatch(/AppIcon/);
  expect(scaffold).toMatch(/Card variant="glass"/);
  expect(scaffold).toMatch(/FITICIAN/);
  expect(signIn).toMatch(/AuthFormCard/);
  expect(signIn).toMatch(/useGoogleSignIn/);
  expect(signIn).toMatch(/publicOnboardingParams/);
});
