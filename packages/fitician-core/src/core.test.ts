import { expect, it } from "vitest";

import {
  createInitialOnboardingState,
  deserializeOnboardingState,
  serializeOnboardingState,
  transitionOnboardingState,
} from "./onboarding.js";
import {
  formatTomanInput,
  irrToRoundedToman,
  tomanToIrr,
} from "./formatters.js";
import {
  GHOST_BACK_PRIVACY_CUT_RATIO,
  GHOST_SIDE_PRIVACY_CUT_RATIO,
  ghostPrivacyCutRatioForView,
} from "./body-ghost.js";

it("runs shared onboarding, currency, and body-privacy contracts", () => {
  const initial = createInitialOnboardingState();
  const selected = transitionOnboardingState(initial, {
    type: "select_product_mode",
    mode: "training",
  });

  expect(selected.step).toBe("shared_profile");
  expect(deserializeOnboardingState(serializeOnboardingState(selected))).toEqual(selected);
  expect(formatTomanInput("۱۲۳۴۵ تومان")).toBe("12,345");
  expect(tomanToIrr("12,345")).toBe(123_450);
  expect(irrToRoundedToman(123_456)).toBe(10_000);
  expect(ghostPrivacyCutRatioForView("side")).toBe(GHOST_SIDE_PRIVACY_CUT_RATIO);
  expect(ghostPrivacyCutRatioForView("back")).toBe(GHOST_BACK_PRIVACY_CUT_RATIO);
});
