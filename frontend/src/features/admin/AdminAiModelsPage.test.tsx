import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import type { AdminAiModel, AdminAiModelsResponse } from "./types";

const adminApi = vi.hoisted(() => ({
  getAdminAiModels: vi.fn(),
  getAdminAiGenerationFailures: vi.fn(),
  getAdminAiModelTestRuns: vi.fn(),
  updateAdminAiRouting: vi.fn(),
  updateAdminAiModel: vi.fn(),
  createAdminAiModel: vi.fn(),
  syncAdminAiModels: vi.fn(),
  testAdminAiModel: vi.fn(),
}));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminAiModelsPage } from "./AdminAiModelsPage";

const freeFirst: AdminAiModel = {
  id: "018f0000-0000-7000-8000-000000000001",
  model_id: "nemotron-3-ultra-free",
  display_name: "Nemotron 3 Ultra Free",
  api_kind: "chat_completions",
  billing_class: "free",
  is_enabled: true,
  priority: 10,
  is_custom: false,
  classification_required: false,
  last_synced_at: null,
  last_checked_at: null,
  last_error_code: null,
  last_error_message: null,
};
const paidModel: AdminAiModel = {
  ...freeFirst,
  id: "018f0000-0000-7000-8000-000000000002",
  model_id: "gpt-5.6-terra",
  display_name: "GPT 5.6 Terra",
  billing_class: "paid",
  priority: 1,
};
const freeSecond: AdminAiModel = {
  ...freeFirst,
  id: "018f0000-0000-7000-8000-000000000003",
  model_id: "big-pickle",
  display_name: "Big Pickle",
  priority: 20,
};

beforeEach(() => {
  adminApi.getAdminAiModels.mockReset();
  adminApi.getAdminAiGenerationFailures.mockReset();
  adminApi.getAdminAiModelTestRuns.mockReset();
  adminApi.updateAdminAiRouting.mockReset();
  adminApi.updateAdminAiModel.mockReset();
  adminApi.createAdminAiModel.mockReset();
  adminApi.syncAdminAiModels.mockReset();
  adminApi.testAdminAiModel.mockReset();
  adminApi.getAdminAiGenerationFailures.mockResolvedValue([]);
  adminApi.getAdminAiModelTestRuns.mockResolvedValue([]);
  adminApi.updateAdminAiRouting.mockResolvedValue({ mode: "automatic", manual_model_id: null });
});

it("sets automatic routing and renders enabled free models in priority order", async () => {
  const page: AdminAiModelsResponse = {
    routing: { mode: "manual", manual_model_id: freeFirst.id },
    models: [freeSecond, paidModel, freeFirst],
  };
  adminApi.getAdminAiModels.mockResolvedValue(page);
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("radio", { name: "خودکار" }));

  expect(adminApi.updateAdminAiRouting).toHaveBeenCalledWith({ mode: "automatic" });
  expect(await screen.findAllByTestId("free-priority-row")).toHaveLength(2);
  expect(screen.getAllByTestId("free-priority-row")[0]).toHaveTextContent("Nemotron 3 Ultra Free");
});

it("shows a classification-required model as unavailable", async () => {
  adminApi.getAdminAiModels.mockResolvedValue({
    routing: { mode: "manual", manual_model_id: freeFirst.id },
    models: [{ ...freeFirst, is_enabled: false, classification_required: true }],
  });
  renderPage();

  expect(await screen.findByText("نیازمند دسته‌بندی")).toBeInTheDocument();
});

it("reindexes duplicate free priorities when moving a later fallback model", async () => {
  const freeThird: AdminAiModel = {
    ...freeSecond,
    id: "018f0000-0000-7000-8000-000000000004",
    model_id: "mimo-v2.5-free",
    display_name: "MiMo 2.5 Free",
  };
  adminApi.getAdminAiModels.mockResolvedValue({
    routing: { mode: "automatic", manual_model_id: null },
    models: [freeFirst, freeSecond, freeThird],
  });
  adminApi.updateAdminAiModel.mockImplementation(
    (modelId: string, update: Partial<AdminAiModel>) => Promise.resolve({
      ...[freeFirst, freeSecond, freeThird].find((model) => model.id === modelId),
      ...update,
    }),
  );
  const user = userEvent.setup();
  renderPage();

  await user.click((await screen.findAllByRole("button", { name: "پایین‌تر" }))[1]);

  expect(adminApi.updateAdminAiModel).toHaveBeenCalledWith(freeSecond.id, { priority: 30 });
});

it("shows a green successful connection message after a model test", async () => {
  adminApi.getAdminAiModels.mockResolvedValue({
    routing: { mode: "manual", manual_model_id: freeFirst.id },
    models: [freeFirst],
  });
  adminApi.testAdminAiModel.mockResolvedValue({
    success: true,
    model: freeFirst,
    test_run: {
      id: "018f0000-0000-7000-8000-000000000020",
      model_id: freeFirst.model_id,
      outcome: "succeeded",
      error_code: null,
      safe_error_message: null,
      created_at: "2026-07-31T12:00:00Z",
    },
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "تست مدل" }));

  const message = await screen.findByText("با موفقیت متصل شد");
  expect(message.closest("article")).toHaveClass("admin-ai-event--success");
});

it("renders recent generation validation failures", async () => {
  adminApi.getAdminAiModels.mockResolvedValue({
    routing: { mode: "manual", manual_model_id: freeFirst.id },
    models: [freeFirst],
  });
  adminApi.getAdminAiGenerationFailures.mockResolvedValue([
    {
      id: "018f0000-0000-7000-8000-000000000010",
      model_id: "nemotron-3-ultra-free",
      created_at: "2026-07-30T20:00:00Z",
      completed_at: "2026-07-30T20:00:05Z",
      error_code: "semantic_validation_failed",
      safe_error_message: "Workout generation returned an invalid plan.",
      validation_diagnostics: [
        {
          model_id: "nemotron-3-ultra-free",
          phase: "repair",
          problems: [
            {
              code: "duplicate_exercise",
              message: "An exercise may not appear twice.",
              day_number: 2,
              exercise_id: "018f0000-0000-7000-8000-000000000099",
            },
          ],
        },
      ],
    },
  ]);
  renderPage();

  expect(await screen.findByText("رویدادهای اخیر هوش مصنوعی")).toBeInTheDocument();
  expect(screen.getByText("semantic_validation_failed")).toBeInTheDocument();
  expect(screen.getByText("duplicate_exercise")).toBeInTheDocument();
  expect(screen.getByText("repair")).toBeInTheDocument();
  expect(screen.getByText("018f0000-0000-7000-8000-000000000099")).toBeInTheDocument();
});

it("renders failed model availability tests as red recent events", async () => {
  adminApi.getAdminAiModels.mockResolvedValue({
    routing: { mode: "manual", manual_model_id: freeFirst.id },
    models: [freeFirst],
  });
  adminApi.getAdminAiModelTestRuns.mockResolvedValue([
    {
      id: "018f0000-0000-7000-8000-000000000021",
      model_id: "unavailable-free-model",
      outcome: "failed",
      error_code: "provider_unavailable",
      safe_error_message: "Workout generation is temporarily unavailable. Please try again.",
      provider_status_code: 400,
      provider_error_type: "invalid_request_error",
      provider_error_message: "Unsupported response_format.",
      created_at: "2026-07-31T11:00:00Z",
    },
  ]);
  renderPage();

  const errorCode = await screen.findByText("provider_unavailable");
  expect(errorCode.closest("article")).toHaveClass("admin-ai-event--error");
  expect(screen.getByText("unavailable-free-model")).toBeInTheDocument();
  expect(screen.getByText("HTTP:", { exact: false })).toBeInTheDocument();
  expect(screen.getByText("Unsupported response_format.")).toBeInTheDocument();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminAiModelsPage />
    </MemoryRouter>,
  );
}
