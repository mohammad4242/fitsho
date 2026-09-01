import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";

const nutritionApi = vi.hoisted(() => ({
  getNutritionMonitoring: vi.fn(),
  triggerNutritionPriceRefresh: vi.fn(),
}));
vi.mock("../nutrition/api", () => nutritionApi);

import { AdminNutritionMonitoringPage } from "./AdminNutritionMonitoringPage";

beforeEach(() => {
  void i18n.changeLanguage("fa");
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
        quotes: [
          {
            id: "quote-1",
            provider_code: "agent_web_digikala",
            source_name: "Digikala",
            source_domain: "digikala.com",
            source_url: "https://digikala.com/product/rice",
            product_title: "برنج ایرانی ۱ کیلوگرم",
            normal_price_toman: "190000",
            promotional_price_toman: "180000",
            normalized_normal_price_toman: "190000",
            package_quantity: "1",
            package_unit: "kg",
            observed_at: "2026-08-09T07:55:00Z",
          },
          {
            id: "quote-2",
            provider_code: "agent_web_okala",
            source_name: "Okala",
            source_domain: "okala.ir",
            source_url: "https://okala.ir/product/rice",
            product_title: "برنج ایرانی ۱ کیلوگرم",
            normal_price_toman: "198000",
            promotional_price_toman: null,
            normalized_normal_price_toman: "198000",
            package_quantity: "1",
            package_unit: "kg",
            observed_at: "2026-08-09T07:56:00Z",
          },
        ],
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
  expect(screen.getByText("پوشش قیمت کافی نیست؛ قیمت زنده ساخته یا حدس زده نمی‌شود.")).toBeInTheDocument();
  expect(screen.queryByText(/api.?key/i)).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "به‌روزرسانی دستی قیمت‌ها" }));

  expect(nutritionApi.triggerNutritionPriceRefresh).toHaveBeenCalledOnce();
  expect(await screen.findByText("اجرای دستی ثبت شد.")).toBeInTheDocument();
});

it("renders the confidence warning and every stored price source as a safe link", async () => {
  await i18n.changeLanguage("en");
  render(
    <MemoryRouter>
      <AdminNutritionMonitoringPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText(/There is not enough confidence to update this price automatically/)).toBeInTheDocument();
  expect(screen.getByText("iranian-rice")).toBeInTheDocument();
  expect(screen.getByText("INSUFFICIENT_SOURCES")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Digikala.*digikala\.com/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Okala.*okala\.ir/ })).toBeInTheDocument();
  expect(screen.getByText(/190,000/)).toBeInTheDocument();
  expect(screen.getByText(/198,000/)).toBeInTheDocument();
  expect(screen.getAllByText("برنج ایرانی ۱ کیلوگرم")).toHaveLength(2);

  const sourceLink = screen.getByRole("link", { name: /Digikala.*digikala\.com/ });
  expect(sourceLink).toHaveAttribute("href", "https://digikala.com/product/rice");
  expect(sourceLink).toHaveAttribute("target", "_blank");
  expect(sourceLink).toHaveAttribute("rel", "noopener noreferrer");
});
