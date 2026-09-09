import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps onboarding guided, native, and RTL-friendly", async () => {
  const source = await readFile(resolve(import.meta.dirname, "OnboardingScreen.tsx"), "utf8");
  const publicSource = await readFile(resolve(import.meta.dirname, "PublicOnboardingScreen.tsx"), "utf8");

  expect(source).toMatch(/getOnboardingSteps/);
  expect(source).toMatch(/ProgressBar/);
  expect(source).toMatch(/modeIcon/);
  expect(source).toMatch(/variant="glass"/);
  expect(source).toMatch(/writingDirection: "rtl"/);
  expect(publicSource).toMatch(/SecurePublicOnboardingDraftStore/);
  expect(publicSource).toMatch(/PUBLIC_ONBOARDING_SOURCE/);
});
