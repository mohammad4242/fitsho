import { render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

jest.mock("@tanstack/react-query", () => ({ useQueryClient: jest.fn(() => ({ invalidateQueries: jest.fn() })) }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn(() => ({ request: jest.fn(), download: jest.fn() })) }));
jest.mock("./nutritionApi", () => ({ createNutritionApi: jest.fn(() => ({ getNutritionProfile: jest.fn(), saveNutritionProfile: jest.fn(), generateEstimate: jest.fn() })) }));

import { NutritionWeightRateCard } from "./NutritionWeightRateCard";
import type { NutritionEstimate } from "./nutritionApi";

function estimateWithRate(overrides: Record<string, unknown> = {}): NutritionEstimate {
  return {
    confidence: "high",
    confidence_reasons: ["WEIGHT_RATE_CLAMPED_FOR_AUTOMATIC_SAFETY"],
    created_at: "2026-09-10T00:00:00Z",
    formula_version: "formula-v1",
    id: "estimate-1",
    input_snapshot: {
      applied_weight_change_kg_per_week: 0.8,
      recommended_weight_change_kg_per_week: 0.5,
      requested_weight_change_kg_per_week: 1.8,
      weight_rate_mode: "safe",
      ...overrides,
    },
    is_stale: false,
    policy_version: "policy-v1",
    revision: 1,
    status: "active",
    targets: {},
  } as unknown as NutritionEstimate;
}

test("renders requested, recommended, and safety-applied weekly rates", () => {
  render(<NutritionWeightRateCard estimate={estimateWithRate()} />);

  expect(screen.getByText("نرخ تغییر وزن هفتگی")).toBeTruthy();
  expect(screen.getByText("تنظیم‌شده برای ایمنی خودکار")).toBeTruthy();
  expect(screen.getByText("درخواست شما")).toBeTruthy();
  expect(screen.getByText("مقدار پیشنهادی")).toBeTruthy();
  expect(screen.getByText("مقدار اعمال‌شده (تنظیم ایمنی)")).toBeTruthy();
  expect(screen.getByText("۱٫۸ کیلوگرم/هفته")).toBeTruthy();
  expect(screen.getByText("۰٫۵ کیلوگرم/هفته")).toBeTruthy();
  expect(screen.getByText("۰٫۸ کیلوگرم/هفته")).toBeTruthy();
});

test("uses the direct-rate wording for an explicit override", () => {
  render(
    <NutritionWeightRateCard
      estimate={estimateWithRate({ weight_rate_mode: "user_override" })}
    />,
  );

  expect(screen.getByText("نرخ دلخواه من")).toBeTruthy();
  expect(screen.getByText("مقدار اعمال‌شده (نرخ مستقیم)")).toBeTruthy();
});

test("keeps the RTL title group intact before the opposite-side mode controls", () => {
  render(<NutritionWeightRateCard estimate={estimateWithRate()} />);

  const title = screen.getByText("نرخ تغییر وزن هفتگی");
  const titleGroup = title.parent?.parent;
  expect(titleGroup).not.toBeNull();
  if (titleGroup === undefined || titleGroup === null) throw new Error("Title group was not rendered");

  expect(titleGroup.props.style).toMatchObject({ flexDirection: "row", flexWrap: "wrap" });
  expect(titleGroup.parent?.props.style).toMatchObject({ flexDirection: "row", flexWrap: "wrap" });
});
