import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("keeps onboarding guided, native, and RTL-friendly", async () => {
  const entrySource = await readFile(resolve(import.meta.dirname, "../app/(public)/index.tsx"), "utf8");
  const source = await readFile(resolve(import.meta.dirname, "OnboardingScreen.tsx"), "utf8");
  const publicSource = await readFile(resolve(import.meta.dirname, "PublicOnboardingScreen.tsx"), "utf8");

  expect(entrySource).toMatch(/public-entry-hero\.jpg/);
  expect(entrySource).toMatch(/Media/);
  expect(source).toMatch(/getOnboardingSteps/);
  expect(source).toMatch(/ProgressBar/);
  expect(source).toMatch(/questionIndex/);
  expect(source).toMatch(/modeIcon/);
  expect(source).toMatch(/variant="glass"/);
  expect(source).toMatch(/writingDirection: "rtl"/);
  expect(source).toMatch(/بیشتر در چه زمینه‌ای به کمک نیاز داری؟/);
  expect(source).toMatch(/برنامه شخصی براساس بدن، هدف، سطح، زمان و تجهیزات/);
  expect(source).toMatch(/getOnboardingStageProgress/);
  expect(source).toMatch(/logout/);
  expect(publicSource).toMatch(/SecurePublicOnboardingDraftStore/);
  expect(publicSource).toMatch(/PUBLIC_ONBOARDING_SOURCE/);
  expect(publicSource).toMatch(/StateSkeleton/);
  expect(publicSource).toMatch(/اطلاعاتت تا زمان ساخت حساب فقط در همین تب نگه‌داری می‌شود/);
  expect(publicSource).toMatch(/شروع با مربی فیتشو/);
  expect(publicSource).toMatch(/برنامه تمرینی/);
  expect(publicSource).toMatch(/برنامه تغذیه/);
  expect(publicSource).toMatch(/حالا حسابت را بساز/);
  expect(publicSource).toMatch(/مسیر امن انتقال اطلاعات/);
  expect(publicSource).toMatch(/getOnboardingStageProgress/);
  expect(publicSource).not.toMatch(/WebView/);
});
