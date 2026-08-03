import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";

const api = vi.hoisted(() => ({
  getAdminAiTaskConfigs: vi.fn(),
  getAdminAiTaskModels: vi.fn(),
  saveAdminAiTaskConfig: vi.fn(),
  testAdminAiProvider: vi.fn(),
  refreshAdminAiModels: vi.fn(),
}));

vi.mock("./api", () => api);

import { AdminAiSettingsPage } from "./AdminAiSettingsPage";
import type { AdminAiTaskConfig } from "./types";

const bodyConfig: AdminAiTaskConfig = {
  task_type: "body_photo_analysis",
  provider: "openrouter",
  enabled: false,
  primary_model_id: null,
  fallback_model_ids: [],
  temperature: 0,
  max_output_tokens: 4096,
  timeout_seconds: 45,
  minimum_confidence: 0.7,
  max_cost_per_request: null,
  routing_restrictions: [],
  credential: { configured: false, masked: null },
  last_successful_connection_test_at: null,
  last_model_catalog_refresh_at: null,
  last_error_code: null,
  last_error_message: null,
};

beforeEach(() => {
  void i18n.changeLanguage("en");
  Object.values(api).forEach((mock) => mock.mockReset());
  api.getAdminAiTaskConfigs.mockResolvedValue([bodyConfig]);
  api.getAdminAiTaskModels.mockResolvedValue({
    refreshed_at: "2026-08-03T12:00:00Z",
    items: [
      {
        provider: "openrouter",
        model_id: "vendor/vision-model",
        display_name: "Vision Model",
        provider_family: "vendor",
        supports_text_input: true,
        supports_image_input: true,
        supports_structured_output: true,
        context_length: 64000,
        input_price_per_token: "0.000001",
        output_price_per_token: "0.000002",
        available: true,
      },
    ],
  });
});

it("shows task-specific vision models and capability details", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findAllByRole("option", { name: /Vision Model/ })).toHaveLength(2);
  await user.selectOptions(screen.getByLabelText("Primary model"), "vendor/vision-model");
  expect(screen.getByText(/Image input/)).toBeInTheDocument();
  expect(screen.getByText(/Structured output/)).toBeInTheDocument();
});

it("requires explicit credential replacement and saves task settings", async () => {
  api.saveAdminAiTaskConfig.mockResolvedValue({
    ...bodyConfig,
    primary_model_id: "vendor/vision-model",
    credential: { configured: true, masked: "••••cret" },
  });
  const user = userEvent.setup();
  renderPage();

  await user.type(await screen.findByLabelText("API key"), "sk-openrouter-secret");
  await user.selectOptions(screen.getByLabelText("Primary model"), "vendor/vision-model");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(api.saveAdminAiTaskConfig).toHaveBeenCalledWith(
    "body_photo_analysis",
    expect.objectContaining({
      api_key: "sk-openrouter-secret",
      replace_credential: true,
      primary_model_id: "vendor/vision-model",
    }),
  );
  expect(await screen.findByText("••••cret")).toBeInTheDocument();
});

it("tests connection and refreshes the dynamic model catalog", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([
    { ...bodyConfig, credential: { configured: true, masked: "••••cret" } },
  ]);
  api.testAdminAiProvider.mockResolvedValue({
    ok: true,
    checked_at: "2026-08-03T12:00:00Z",
    model_count: 2,
    error_code: null,
    safe_error_message: null,
  });
  api.refreshAdminAiModels.mockResolvedValue({
    provider: "openrouter",
    model_count: 2,
    refreshed_at: "2026-08-03T12:00:00Z",
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Test connection" }));
  expect(await screen.findByText("Connection successful")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Refresh models" }));
  expect(api.refreshAdminAiModels).toHaveBeenCalledTimes(1);
  expect(api.getAdminAiTaskModels).toHaveBeenCalledTimes(2);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminAiSettingsPage />
    </MemoryRouter>,
  );
}
