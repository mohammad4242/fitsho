import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps auth screens on a quiet Web-aligned native scaffold", async () => {
  const scaffold = await readFile(resolve(import.meta.dirname, "AuthScaffold.tsx"), "utf8");
  const signIn = await readFile(resolve(import.meta.dirname, "../app/(auth)/auth/sign-in.tsx"), "utf8");
  const register = await readFile(resolve(import.meta.dirname, "../app/(auth)/auth/register.tsx"), "utf8");

  expect(scaffold).toMatch(/authCopy\.common\.brand/);
  expect(scaffold).toMatch(/PageHeading/);
  expect(scaffold).toMatch(/Screen/);
  expect(scaffold).toMatch(/eyebrow\?: string/);
  expect(scaffold).not.toMatch(/CinematicSurface/);
  expect(scaffold).not.toMatch(/Card/);
  expect(scaffold).not.toMatch(/AppIcon/);
  expect(scaffold).not.toMatch(/accentRule/);
  expect(signIn).toMatch(/SegmentedControl/);
  expect(signIn).not.toMatch(/AuthFormCard/);
  expect(signIn).toMatch(/useGoogleSignIn/);
  expect(signIn).toMatch(/useAppleSignIn/);
  expect(signIn).toMatch(/AppleAuthenticationButton/);
  expect(signIn).toMatch(/publicOnboardingParams/);
  expect(signIn).toMatch(/verifyPhoneOtp/);
  expect(signIn).toMatch(/sendPhoneOtp/);
  expect(signIn).toMatch(/validateOtpCode/);
  expect(register).toMatch(/passwordHint/);
  expect(register).toMatch(/maxLength=\{128\}/);
});
