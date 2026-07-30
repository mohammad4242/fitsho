import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import type { AdminAiModel, AdminAiModelsResponse } from "./types";

const adminApi = vi.hoisted(() => ({
  getAdminAiModels: vi.fn(),
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
  adminApi.updateAdminAiRouting.mockReset();
  adminApi.updateAdminAiModel.mockReset();
  adminApi.createAdminAiModel.mockReset();
  adminApi.syncAdminAiModels.mockReset();
  adminApi.testAdminAiModel.mockReset();
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

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminAiModelsPage />
    </MemoryRouter>,
  );
}
