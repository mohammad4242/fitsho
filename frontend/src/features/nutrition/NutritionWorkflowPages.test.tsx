import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import * as api from "./api";
import { NutritionLabsPage } from "./NutritionLabsPage";
import { NutritionSupplementsPage } from "./NutritionSupplementsPage";
import { NutritionTrackingPage } from "./NutritionTrackingPage";
import { PhysicianNutritionReviewPage } from "./PhysicianNutritionReviewPage";
import type { DailyTrackingSummary, NutritionAdherence, WeeklyPlan } from "./types";

vi.mock("./api");

const today = new Date().toISOString().slice(0, 10);

const summary: DailyTrackingSummary = {
  entry_date: today,
  check_in_status: "mostly_on_plan",
  plan_revision_id: "plan-1",
  data_status: "sufficient",
  actual_totals: { energy_kcal: 1750, protein_g: 92 },
  entries: [{
    id: "entry-1",
    entry_date: today,
    plan_revision_id: null,
    planned_meal_id: null,
    food_id: "food-1",
    display_name: "Chicken breast",
    quantity_grams: 100,
    source: "catalogue_manual",
    confidence: "high",
    nutrients: { energy_kcal: 165, protein_g: 31 },
    warning_codes: [],
  }],
};

const adherence: NutritionAdherence = {
  start: today,
  end: today,
  days: [{
    date: today,
    status: "sufficient",
    calorie_adherence: 88,
    protein_adherence: 92,
    meal_adherence: 75,
    tracking_completeness: 90,
    exact_entry_ratio: 1,
    composite_score: 87,
    formula_version: "adherence-v1",
    planned: { energy_kcal: 2000, protein_g: 100 },
    actual: { energy_kcal: 1750, protein_g: 92 },
  }],
  weight_trend: [],
  weight_causality_claimed: false,
};

const physicianPlan = {
  id: "plan-1",
  revision: 1,
  weekly_cost_irr: 7_000_000,
  budget_status: "within_budget",
  input_snapshot: { safety_reason_codes: [] },
  price_snapshot: { status: "fresh" },
  food_data_manifest: { catalogue_version: "v1" },
  nutrients: {
    protein: { nutrient_code: "protein", planned: 100, unit: "g/day", status: "adequate" },
  },
  days: [{
    plan_date: today,
    meals: [{
      id: "meal-1",
      foods: [{ food_id: "food-1", name_fa: "سینه مرغ", name_en: "Chicken breast", grams: 100 }],
    }],
  }],
} as unknown as WeeklyPlan;

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  vi.mocked(api.getDailyTracking).mockResolvedValue(summary);
  vi.mocked(api.getNutritionAdherence).mockResolvedValue(adherence);
  vi.mocked(api.listCatalogueFoods).mockResolvedValue([
    { id: "food-1", slug: "chicken", name_fa: "سینه مرغ", name_en: "Chicken breast", canonical_unit: "g" },
    { id: "food-2", slug: "lentils", name_fa: "عدس", name_en: "Lentils", canonical_unit: "g" },
  ]);
  vi.mocked(api.listRecentFoods).mockResolvedValue([]);
  vi.mocked(api.getTrackingHistory).mockResolvedValue([summary]);
  vi.mocked(api.listLabDocuments).mockResolvedValue([]);
  vi.mocked(api.listLabRequests).mockResolvedValue([]);
  vi.mocked(api.listSupplementOrders).mockResolvedValue([]);
  vi.mocked(api.listPhysicianReviews).mockResolvedValue([]);
  vi.mocked(api.listSupplementCatalogue).mockResolvedValue([]);
  vi.mocked(api.listPhysicianSupplementOrders).mockResolvedValue([]);
});

it("shows planned versus actual tracking and saves photo corrections before confirmation", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listRecentFoods).mockResolvedValue([{ food_id: "food-1", display_name: "Chicken breast", last_quantity_grams: 120, last_entry_date: today }]);
  vi.mocked(api.estimateFoodPhoto).mockResolvedValue({
    id: "estimate-1",
    overall_confidence: 0.8,
    needs_user_confirmation: true,
    items: [{ item_id: "item-1", food_id: "food-1", name_guess: "Chicken", estimated_amount: 120, unit: "g", mapping_status: "verified" }],
  });
  vi.mocked(api.correctFoodPhotoItem).mockResolvedValue({
    id: "estimate-1",
    overall_confidence: 0.8,
    needs_user_confirmation: true,
    items: [{ item_id: "item-1", food_id: "food-1", name_guess: "Chicken", estimated_amount: 150, unit: "g", mapping_status: "verified" }],
  });
  render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

  expect(await screen.findByText("Logged calories")).toBeInTheDocument();
  expect(screen.getByText("Planned calories")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Chicken breast · 120 g" })).toBeInTheDocument();
  await user.click(screen.getByRole("checkbox", { name: /third-party image processing/i }));
  await user.upload(screen.getByLabelText("Choose food photo"), new File(["image"], "meal.jpg", { type: "image/jpeg" }));
  const amount = await screen.findByRole("spinbutton", { name: "Chicken amount" });
  await user.clear(amount);
  await user.type(amount, "150");
  await user.tab();

  await waitFor(() => expect(api.correctFoodPhotoItem).toHaveBeenCalledWith("estimate-1", "item-1", { estimated_amount: 150 }));
});

it("uploads laboratory metadata and can delete an owned document", async () => {
  const user = userEvent.setup();
  const document = { id: "lab-1", original_filename: "cbc.pdf", content_type: "application/pdf", byte_size: 10, test_date: today, laboratory_name: "Lab", user_note: null, category: "CBC", review_status: "uploaded", review_notes: null, uploaded_at: `${today}T12:00:00Z` };
  vi.mocked(api.listLabDocuments)
    .mockResolvedValueOnce([document])
    .mockResolvedValueOnce([document])
    .mockResolvedValueOnce([]);
  vi.mocked(api.uploadLabDocument).mockResolvedValue({});
  vi.mocked(api.deleteLabDocument).mockResolvedValue();
  render(<MemoryRouter><NutritionLabsPage /></MemoryRouter>);

  expect(await screen.findByText("cbc.pdf")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Laboratory name"), "Fitsho Lab");
  await user.type(screen.getByLabelText("Category"), "Blood panel");
  await user.upload(screen.getByLabelText("Choose lab file"), new File(["pdf"], "result.pdf", { type: "application/pdf" }));
  await waitFor(() => expect(api.uploadLabDocument).toHaveBeenCalledWith(expect.any(File), expect.objectContaining({ laboratoryName: "Fitsho Lab", category: "Blood panel" })));
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await waitFor(() => expect(api.deleteLabDocument).toHaveBeenCalledWith("lab-1"));
});

it("filters the member supplement history without exposing dose editing", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listSupplementOrders).mockResolvedValue([
    { id: "order-1", plan_id: "plan-1", supplement_id: "supplement-1", name: "Vitamin D", dose_amount: 1, dose_unit: "unit", daily_units: 1, frequency: "daily", duration_days: 30, instructions: "After food", rationale: null, status: "active", acknowledged_at: null, supplement_nutrient_contribution: {}, combined_exposure_safety: {} },
    { id: "order-2", plan_id: "plan-0", supplement_id: "supplement-2", name: "Iron", dose_amount: 1, dose_unit: "unit", daily_units: 1, frequency: "daily", duration_days: 14, instructions: "As directed", rationale: null, status: "completed", acknowledged_at: today, supplement_nutrient_contribution: {}, combined_exposure_safety: {} },
  ]);
  render(<MemoryRouter><NutritionSupplementsPage /></MemoryRouter>);

  expect(await screen.findByText("Vitamin D")).toBeInTheDocument();
  await user.selectOptions(screen.getByRole("combobox", { name: "Status" }), "completed");
  expect(screen.queryByText("Vitamin D")).not.toBeInTheDocument();
  expect(screen.getByText("Iron")).toBeInTheDocument();
  expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
});

it("lets a physician claim an exact revision and choose replacements from the canonical catalogue", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listPhysicianReviews).mockResolvedValue([{ review_id: "review-1", plan_id: "plan-1", user_id: "user-1", member_display_name: "Member One", status: "pending", priority: 1, physician_user_id: null, requested_at: today, target_review_by: null, reviewed_at: null, overdue: false }]);
  vi.mocked(api.claimPhysicianReview).mockResolvedValue({});
  vi.mocked(api.getPhysicianPlan).mockResolvedValue(physicianPlan);
  vi.mocked(api.listPhysicianLabs).mockResolvedValue([]);
  vi.mocked(api.replacePhysicianFood).mockResolvedValue(physicianPlan);
  render(<MemoryRouter><PhysicianNutritionReviewPage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "Claim and view revision" }));
  expect(await screen.findByText("Revision under review 1")).toBeInTheDocument();
  expect(screen.getByText("Nutrient validation")).toBeInTheDocument();
  await user.selectOptions(screen.getByRole("combobox", { name: "Replace Chicken breast" }), "food-2");
  await waitFor(() => expect(api.replacePhysicianFood).toHaveBeenCalledWith("plan-1", "meal-1", "food-1", "food-2"));
});

it("separates physician queue views and keeps approved revisions read-only", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listPhysicianReviews).mockImplementation(async (view = "pending") => view === "approved"
    ? [{ review_id: "approved-1", plan_id: "plan-1", user_id: "user-1", member_display_name: "Member One", status: "approved", priority: 1, physician_user_id: "physician-1", requested_at: today, target_review_by: null, reviewed_at: today, overdue: false }]
    : []);
  vi.mocked(api.getPhysicianPlan).mockResolvedValue(physicianPlan);
  vi.mocked(api.listPhysicianLabs).mockResolvedValue([]);
  vi.mocked(api.listPhysicianSupplementOrders).mockResolvedValue([]);
  render(<MemoryRouter><PhysicianNutritionReviewPage /></MemoryRouter>);

  expect(await screen.findByRole("tab", { name: /Approved \(1\)/ })).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: /Approved/ }));
  await user.click(screen.getByRole("button", { name: "View revision" }));
  expect(await screen.findByText("Revision under review 1")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve this revision" })).not.toBeInTheDocument();
  expect(screen.getByRole("spinbutton", { name: "Chicken breast quantity" })).toBeDisabled();
});

it("lays out physician cases in a desk sidebar with clinical workspace tabs", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listPhysicianReviews).mockResolvedValue([
    { review_id: "review-1", plan_id: "plan-1", user_id: "user-1", member_display_name: "Member One", status: "pending", priority: 1, physician_user_id: null, requested_at: today, target_review_by: null, reviewed_at: null, overdue: false },
  ]);
  render(<MemoryRouter><PhysicianNutritionReviewPage /></MemoryRouter>);

  expect(await screen.findByText("Physician desk")).toBeInTheDocument();
  expect(screen.getByText("Member One").closest("aside")).toHaveClass("physician-review-queue");
  vi.mocked(api.claimPhysicianReview).mockResolvedValue({});
  vi.mocked(api.getPhysicianPlan).mockResolvedValue(physicianPlan);
  vi.mocked(api.listPhysicianLabs).mockResolvedValue([]);
  await user.click(screen.getByRole("button", { name: "Claim and view revision" }));
  expect(screen.getByRole("tab", { name: "Plan review" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Laboratory review" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Supplements" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Notes" })).toBeInTheDocument();
});
