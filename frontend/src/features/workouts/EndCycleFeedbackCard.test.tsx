import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCurrentCompletionFeedback: vi.fn(),
  saveCurrentCompletionFeedback: vi.fn(),
}));

vi.mock("./api", () => api);

import { EndCycleFeedbackCard } from "./EndCycleFeedbackCard";

const dueContext = {
  cycle_id: "cycle-1",
  status: "active" as const,
  duration_weeks: 4 as const,
  current_week: 4,
  is_due: true,
  feedback_id: null,
  feedback: null,
  submitted_at: null,
};

beforeEach(() => {
  api.getCurrentCompletionFeedback.mockReset();
  api.saveCurrentCompletionFeedback.mockReset();
  api.getCurrentCompletionFeedback.mockResolvedValue(dueContext);
  api.saveCurrentCompletionFeedback.mockResolvedValue({
    ...dueContext,
    status: "completed",
    is_due: false,
    feedback_id: "feedback-1",
  });
});

afterEach(() => vi.restoreAllMocks());

it("shows the end-of-cycle form only when the cycle is due", async () => {
  render(<EndCycleFeedbackCard />);

  expect(await screen.findByRole("heading", { name: "بازخورد پایان دوره" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "سختی کلی برنامه" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "ریکاوری کلی" })).toBeInTheDocument();
  expect(screen.getByRole("combobox", { name: "رضایت کلی" })).toBeInTheDocument();
});

it("keeps end-of-cycle feedback discoverable and explains the lock before the cycle ends", async () => {
  const user = userEvent.setup();
  api.getCurrentCompletionFeedback.mockResolvedValue({
    ...dueContext,
    current_week: 2,
    is_due: false,
  });

  render(<EndCycleFeedbackCard />);

  const trigger = await screen.findByRole("button", { name: "بازخورد پایان دوره" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  await user.click(trigger);

  expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(
    screen.getByText(
      "پس از اتمام دوره ۴ هفته‌ای، این فرم برای هدفمندتر شدن برنامه بعدی فعال می‌شود. لطفاً فرم را کامل و با دقت پر کنید.",
    ),
  ).toBeVisible();
});

it("submits structured feedback and shows the completed state", async () => {
  const user = userEvent.setup();
  render(<EndCycleFeedbackCard />);

  await screen.findByRole("heading", { name: "بازخورد پایان دوره" });
  await user.selectOptions(screen.getByRole("combobox", { name: "ریکاوری کلی" }), "poor");
  await user.type(screen.getByLabelText("یادداشت اختیاری"), "ریکاوری سخت بود.");
  await user.click(screen.getByRole("button", { name: "ثبت بازخورد پایان دوره" }));

  await waitFor(() => expect(api.saveCurrentCompletionFeedback).toHaveBeenCalledWith({
    overall_difficulty: "appropriate",
    overall_recovery: "poor",
    overall_satisfaction: "neutral",
    strength_progress: "unchanged",
    muscle_progress: "unchanged",
    endurance_progress: "unchanged",
    energy_progress: "unchanged",
    performance_changes: null,
    pain_or_limitation_feedback: null,
    note_optional: "ریکاوری سخت بود.",
  }));
  expect(await screen.findByText("بازخورد پایان دوره ثبت شد")).toBeInTheDocument();
});

it("keeps the page usable when the feedback API is unavailable", async () => {
  api.getCurrentCompletionFeedback.mockRejectedValue(new Error("offline"));
  render(<EndCycleFeedbackCard />);

  expect(await screen.findByRole("alert")).toHaveTextContent("بازخورد پایان دوره دریافت نشد");
});
