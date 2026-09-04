import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

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
    macro_totals: { calories: 200, protein_g: 25, carbohydrate_g: 0, fat_g: 5 },
    macro_totals_complete: true,
    items: [{ item_id: "item-1", food_id: "food-1", name_guess: "Chicken", estimated_amount: 120, unit: "g", mapping_status: "verified" }],
  });
  vi.mocked(api.correctFoodPhotoItem).mockResolvedValue({
    id: "estimate-1",
    overall_confidence: 0.8,
    needs_user_confirmation: true,
    macro_totals: { calories: 250, protein_g: 30, carbohydrate_g: 0, fat_g: 6 },
    macro_totals_complete: true,
    items: [{ item_id: "item-1", food_id: "food-1", name_guess: "Chicken", estimated_amount: 150, unit: "g", mapping_status: "verified" }],
  });
  render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

  expect(await screen.findByText("Logged calories")).toBeInTheDocument();
  expect(screen.getByText("Planned calories")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "Chicken breast · 120 g" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /Food photo/i }));
  await user.click(screen.getByRole("checkbox", { name: /third-party image processing/i }));
  await user.upload(screen.getByLabelText("Choose food photo"), new File(["image"], "meal.jpg", { type: "image/jpeg" }));
  expect(await screen.findByRole("img", { name: "Meal photo preview" })).toBeInTheDocument();
  expect(screen.getByText(/≈ 200/)).toBeInTheDocument();
  const amount = await screen.findByRole("spinbutton", { name: "Chicken amount" });
  await user.clear(amount);
  await user.type(amount, "150");
  await user.tab();

  await waitFor(() => expect(api.correctFoodPhotoItem).toHaveBeenCalledWith("estimate-1", "item-1", { estimated_amount: 150 }));
});

it("keeps adherence rows collapsed while the date filter remains active", async () => {
  const user = userEvent.setup();
  render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

  const toggle = await screen.findByRole("button", { name: "Adherence trend" });
  const date = screen.getByLabelText("From");
  const contentId = toggle.getAttribute("aria-controls");
  const content = contentId ? document.getElementById(contentId) : null;
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(content).toHaveAttribute("aria-hidden", "true");
  expect(date).toBeEnabled();

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(content).toHaveAttribute("aria-hidden", "false");

  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");

  await waitFor(() => expect(api.getTrackingHistory).toHaveBeenCalled());
  vi.mocked(api.getNutritionAdherence).mockClear();
  vi.mocked(api.getTrackingHistory).mockClear();
  const selectedStart = `${today.slice(0, 8)}01`;
  fireEvent.change(date, { target: { value: selectedStart } });

  await waitFor(() => {
    expect(api.getNutritionAdherence).toHaveBeenCalledWith(selectedStart, today);
    expect(api.getTrackingHistory).toHaveBeenCalledWith(selectedStart, today);
  });
});

it("keeps exact catalogue and quick estimate submissions unchanged", async () => {
  const user = userEvent.setup();
  vi.mocked(api.addCatalogueFoodEntry).mockResolvedValue({});
  vi.mocked(api.addQuickApproximation).mockResolvedValue({});
  render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

  await user.click(await screen.findByText("Log food manually"));
  const catalogueGroup = screen.getByRole("group", { name: "Exact catalogue entry" });
  await user.selectOptions(within(catalogueGroup).getByRole("combobox", { name: "Food" }), "food-2");
  const grams = within(catalogueGroup).getByRole("spinbutton", { name: "Amount in grams" });
  await user.clear(grams);
  await user.type(grams, "175");
  await user.click(within(catalogueGroup).getByRole("button", { name: "Add catalogue food" }));

  await waitFor(() => expect(api.addCatalogueFoodEntry).toHaveBeenCalledWith({
    entry_date: today,
    food_id: "food-2",
    grams: 175,
    note: null,
  }));

  const estimateGroup = screen.getByRole("group", { name: "Quick estimate" });
  await user.type(within(estimateGroup).getByRole("textbox", { name: "Approximate calories" }), "430");
  await user.click(within(estimateGroup).getByRole("button", { name: "Add estimate" }));

  await waitFor(() => expect(api.addQuickApproximation).toHaveBeenCalledWith({
    entry_date: today,
    display_name: "Approximate meal",
    calories: 430,
    protein_g: null,
  }));
});

it("uploads laboratory metadata and can delete an owned document", async () => {
  const user = userEvent.setup();
  const document = { id: "lab-1", original_filename: "cbc.pdf", content_type: "application/pdf", byte_size: 10, test_date: today, laboratory_name: "Lab", user_note: "Annual panel", category: "CBC", review_status: "uploaded", review_notes: null, uploaded_at: `${today}T12:00:00Z` };
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
  await user.type(screen.getByLabelText("Note"), "Annual panel");
  await user.upload(screen.getByLabelText("Choose lab file"), new File(["pdf"], "result.pdf", { type: "application/pdf" }));
  expect(screen.getByText("result.pdf")).toBeInTheDocument();
  const labCard = screen.getByText("cbc.pdf").closest("article");
  expect(labCard).not.toBeNull();
  if (labCard) {
    expect(within(labCard).getByText("CBC")).toBeInTheDocument();
    expect(within(labCard).getByText("Annual panel")).toBeInTheDocument();
    expect(within(labCard).getByText("Uploaded")).toBeInTheDocument();
  }
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

describe("Food photo nutrition estimation redesigned flow", () => {
  const completeEstimate: api.FoodPhotoEstimate = {
    id: "estimate-1",
    overall_confidence: 0.85,
    needs_user_confirmation: true,
    macro_totals: { calories: 350, protein_g: 40, carbohydrate_g: 20, fat_g: 10 },
    macro_totals_complete: true,
    items: [
      {
        item_id: "item-1",
        food_id: "food-1",
        name_guess: "Chicken breast",
        estimated_amount: 150,
        unit: "g",
        mapping_status: "resolved",
      },
    ],
  };

  const incompleteEstimate: api.FoodPhotoEstimate = {
    id: "estimate-2",
    overall_confidence: 0.7,
    needs_user_confirmation: true,
    macro_totals: { calories: 200, protein_g: 25, carbohydrate_g: 0, fat_g: 5 },
    macro_totals_complete: false,
    items: [
      {
        item_id: "item-1",
        food_id: "food-1",
        name_guess: "Chicken breast",
        estimated_amount: 100,
        unit: "g",
        mapping_status: "resolved",
      },
      {
        item_id: "item-2",
        food_id: null,
        name_guess: "Unknown sauce",
        estimated_amount: 50,
        unit: "unknown",
        mapping_status: "unresolved",
      },
    ],
  };

  async function openAndUpload(user: ReturnType<typeof userEvent.setup>) {
    expect(await screen.findByText("Logged calories")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Food photo/i }));
    await user.click(screen.getByRole("checkbox", { name: /third-party image processing/i }));
    const fileInput = screen.getByLabelText("Choose food photo");
    await waitFor(() => expect(fileInput).toBeEnabled());
    await user.upload(
      fileInput,
      new File(["image"], "meal.jpg", { type: "image/jpeg" })
    );
    expect(await screen.findByRole("img", { name: "Meal photo preview" })).toBeInTheDocument();
  }

  it("A: renders calories prominently and macros immediately after upload", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);

    expect(await screen.findByText("Estimated calories")).toBeInTheDocument();
    expect(screen.getByText("≈ 350 kcal")).toBeInTheDocument();
    expect(screen.getByText("≈ 40 g")).toBeInTheDocument();
    expect(screen.getByText("≈ 20 g")).toBeInTheDocument();
    expect(screen.getByText("≈ 10 g")).toBeInTheDocument();
    expect(screen.queryByText(/Partial estimate/i)).not.toBeInTheDocument();
  });

  it("B: keeps detection details collapsed by default", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    const { container } = render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    await screen.findByText("Estimated calories");

    const details = container.querySelector("details.nutrition-photo-details");
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute("open");
  });

  it("C: allows updating item amount in detection details", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    vi.mocked(api.correctFoodPhotoItem).mockResolvedValue({
      ...completeEstimate,
      macro_totals: { calories: 420, protein_g: 48, carbohydrate_g: 20, fat_g: 12 },
      items: [{ ...completeEstimate.items[0], estimated_amount: 180 }],
    });
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    const amountInput = await screen.findByRole("spinbutton", { name: "Chicken breast amount" });
    await user.clear(amountInput);
    await user.type(amountInput, "180");
    await user.tab();

    await waitFor(() =>
      expect(api.correctFoodPhotoItem).toHaveBeenCalledWith("estimate-1", "item-1", {
        estimated_amount: 180,
      })
    );
  });

  it("D: allows removing an item from the estimate", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    vi.mocked(api.correctFoodPhotoItem).mockResolvedValue({
      ...completeEstimate,
      items: [],
      macro_totals: { calories: 0, protein_g: 0, carbohydrate_g: 0, fat_g: 0 },
    });
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    const removeBtn = await screen.findByRole("button", { name: "Remove" });
    await user.click(removeBtn);

    await waitFor(() =>
      expect(api.correctFoodPhotoItem).toHaveBeenCalledWith("estimate-1", "item-1", {
        remove: true,
      })
    );
  });

  it("E: displays Needs review and food catalogue selector for unresolved items", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(incompleteEstimate);
    vi.mocked(api.correctFoodPhotoItem).mockResolvedValue({
      ...completeEstimate,
      id: "estimate-2",
    });
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    expect(await screen.findByText("Needs review")).toBeInTheDocument();
    expect(screen.getByText("Matched")).toBeInTheDocument();

    const select = screen.getByRole("combobox", { name: "Choose food for Unknown sauce" });
    await user.selectOptions(select, "food-2");
    const gramInput = screen.getByRole("spinbutton", { name: "Unknown sauce amount in grams" });
    await user.type(gramInput, "60");

    const applyBtn = screen.getByRole("button", { name: "Apply" });
    expect(applyBtn).toBeEnabled();
    await user.click(applyBtn);

    await waitFor(() =>
      expect(api.correctFoodPhotoItem).toHaveBeenCalledWith("estimate-2", "item-2", {
        food_id: "food-2",
        estimated_amount: 60,
      })
    );
  });

  it("F: disables confirm button and displays guidance when estimate is incomplete", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(incompleteEstimate);
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    expect(await screen.findByText("Partial estimate — review the items below to complete the result.")).toBeInTheDocument();

    const confirmBtn = screen.getByRole("button", { name: "Confirm and log" });
    expect(confirmBtn).toBeDisabled();
  });

  it("G: enables confirm button and logs food once estimate is complete", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    vi.mocked(api.confirmFoodPhoto).mockResolvedValue({});
    render(<MemoryRouter><NutritionTrackingPage /></MemoryRouter>);

    await openAndUpload(user);
    const confirmBtn = await screen.findByRole("button", { name: "Confirm and log" });
    expect(confirmBtn).toBeEnabled();

    await user.click(confirmBtn);
    await waitFor(() =>
      expect(api.confirmFoodPhoto).toHaveBeenCalledWith("estimate-1", today)
    );
  });

  it("H: confirms Free Meal preview and preserves return navigation", async () => {
    const user = userEvent.setup();
    vi.mocked(api.estimateFoodPhoto).mockResolvedValue(completeEstimate);
    vi.mocked(api.confirmFreeMealPhotoPreview).mockResolvedValue({
      calories: 350,
      protein_g: 40,
      carbohydrate_g: 20,
      fat_g: 10,
    });
    render(
      <MemoryRouter initialEntries={["/tracking?freeMealId=meal-42&return=/nutrition-estimate"]}>
        <NutritionTrackingPage />
      </MemoryRouter>
    );

    expect(await screen.findByText("Logged calories")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /third-party image processing/i }));
    const fileInput = screen.getByLabelText("Choose food photo");
    await waitFor(() => expect(fileInput).toBeEnabled());
    await user.upload(
      fileInput,
      new File(["image"], "meal.jpg", { type: "image/jpeg" })
    );
    expect(await screen.findByRole("img", { name: "Meal photo preview" })).toBeInTheDocument();

    const confirmBtn = await screen.findByRole("button", {
      name: "Confirm and return to Free Meal",
    });
    expect(confirmBtn).toBeEnabled();
    await user.click(confirmBtn);

    await waitFor(() =>
      expect(api.confirmFreeMealPhotoPreview).toHaveBeenCalledWith("estimate-1")
    );
  });
});
