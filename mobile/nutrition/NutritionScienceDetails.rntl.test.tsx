import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

jest.mock("expo-router", () => ({ useRouter: jest.fn(() => ({ push: jest.fn() })) }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { NutritionScienceDetails } from "./NutritionScienceDetails";
import type { NutritionEstimate } from "./nutritionApi";

const estimate = {
  confidence: "high",
  confidence_reasons: [],
  created_at: "2026-09-10T00:00:00Z",
  formula_version: "nutrition-formula-v1",
  id: "estimate-1",
  is_stale: false,
  micronutrients: {
    calcium_mg: {
      applicable_population: "adult",
      aggregation_window: "day",
      confidence: "high",
      explanation_codes: [],
      policy_version: "ref-v1",
      reference_kind: "RDA",
      source_reference: "source",
      target_value: 1000,
      unit: "mg/day",
      unit_form: "mg",
      upper_limit_kind: null,
      upper_limit_scope: "day",
      upper_limit_value: null,
    },
  },
  policy_version: "nutrition-science-v1",
  revision: 2,
  status: "active",
  targets: {
    fibre: { confidence: "high", explanation_codes: [], maximum: 45, minimum: 25, preferred: 30, preferred_maximum: 35, source_ids: [], unit: "g/day" },
    free_sugar: { confidence: "high", explanation_codes: [], maximum: 50, minimum: null, preferred: null, preferred_maximum: 25, source_ids: [], unit: "g/day" },
    saturated_fat: { confidence: "high", explanation_codes: [], maximum: 20, minimum: null, preferred: null, preferred_maximum: null, source_ids: [], unit: "g/day" },
    sodium: { confidence: "high", explanation_codes: [], maximum: 2300, minimum: null, preferred: null, preferred_maximum: null, source_ids: [], unit: "mg/day" },
    trans_fat: { confidence: "high", explanation_codes: [], maximum: 2, minimum: null, preferred: null, preferred_maximum: null, source_ids: [], unit: "g/day" },
  },
} as unknown as NutritionEstimate;

test("keeps scientific details collapsed and exposes exact safety targets when opened", () => {
  render(<NutritionScienceDetails estimate={estimate} />);

  const disclosure = screen.getByRole("button", { name: "جزئیات علمی و حدود ایمنی" });
  expect(disclosure.props.accessibilityState).toEqual({ expanded: false });
  fireEvent.press(disclosure);

  expect(screen.getByText("فیبر")).toBeTruthy();
  expect(screen.getByText("حداقل مطلق ۲۵ گرم")).toBeTruthy();
  expect(screen.getByText("قند آزاد")).toBeTruthy();
  expect(screen.getByText("حد ترجیحی ۲۵ گرم")).toBeTruthy();
  expect(screen.getByText("چربی اشباع")).toBeTruthy();
  expect(screen.getByText("چربی ترانس")).toBeTruthy();
  expect(screen.getByText("سدیم")).toBeTruthy();
  expect(screen.getByText("مرجع ریزمغذی‌ها")).toBeTruthy();
  expect(screen.getByText("۱٬۰۰۰ mg/day")).toBeTruthy();
  expect(screen.getByText("این یک برآورد علمی است، نه تشخیص یا نسخه پزشکی. نتیجه واقعی با پایش وزن، انرژی و عملکرد اصلاح می‌شود.")).toBeTruthy();
  expect(screen.getByText("nutrition-science-v1")).toBeTruthy();
});
