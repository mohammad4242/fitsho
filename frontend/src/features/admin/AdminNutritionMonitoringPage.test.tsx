import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const nutritionApi = vi.hoisted(() => ({
  getNutritionMonitoring: vi.fn(),
  triggerNutritionPriceRefresh: vi.fn(),
}));
vi.mock("../nutrition/api", () => nutritionApi);

import { AdminNutritionMonitoringPage } from "./AdminNutritionMonitoringPage";

beforeEach(() => {
  nutritionApi.getNutritionMonitoring.mockReset();
  nutritionApi.triggerNutritionPriceRefresh.mockReset();
  nutritionApi.getNutritionMonitoring.mockResolvedValue({
    counts: {
      foods: 67,
      meals: 0,
      accepted_price_references: 0,
      price_reviews: 1,
      supplements: 0,
    },
    coverage_warning: "INSUFFICIENT_PRICE_COVERAGE",
    provider_health: [
      {
        code: "digikala",
        enabled: false,
        last_success_at: null,
        last_error: "HTTP 429",
        parser_version: "public-page-v1",
      },
    ],
    price_reviews: [
      {
        id: "review-1",
        food_slug: "iranian-rice",
        reason_codes: ["INSUFFICIENT_SOURCES"],
        candidate_reference_price_toman: "250000",
        created_at: "2026-08-09T08:00:00Z",
      },
    ],
    broken_mappings: [],
    recent_price_runs: [],
  });
});

it("shows source health, coverage exceptions, and triggers a manual refresh", async () => {
  nutritionApi.triggerNutritionPriceRefresh.mockResolvedValue({
    status: "completed_with_errors",
  });
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <AdminNutritionMonitoringPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("digikala")).toBeInTheDocument();
  expect(screen.getByText("INSUFFICIENT_SOURCES")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("پوشش قیمت کافی نیست");
  expect(screen.queryByText(/api.?key/i)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "به‌روزرسانی دستی قیمت‌ها" }));

  expect(nutritionApi.triggerNutritionPriceRefresh).toHaveBeenCalledOnce();
  expect(await screen.findByText("اجرای دستی ثبت شد.")).toBeInTheDocument();
});
