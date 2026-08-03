import { render, screen, waitFor } from "@testing-library/react";
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
import type { AdminAiCatalogResponse, AdminAiTaskConfig } from "./types";

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

const progressConfig: AdminAiTaskConfig = {
  ...bodyConfig,
  task_type: "progress_comparison",
};

beforeEach(() => {
  void i18n.changeLanguage("en");
  Object.values(api).forEach((mock) => mock.mockReset());
  api.getAdminAiTaskConfigs.mockResolvedValue([bodyConfig]);
  api.getAdminAiTaskModels.mockResolvedValue({
    refreshed_at: "2026-08-03T12:00:00Z",
    stale: false,
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

it("persists disable immediately", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([{ ...bodyConfig, enabled: true }]);
  api.saveAdminAiTaskConfig.mockResolvedValue({ ...bodyConfig, enabled: false });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Disable" }));

  expect(api.saveAdminAiTaskConfig).toHaveBeenCalledWith(
    "body_photo_analysis",
    expect.objectContaining({ enabled: false, replace_credential: false }),
  );
});

it("renders persisted observability for the selected task", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([
    {
      ...bodyConfig,
      last_successful_connection_test_at: "2026-08-03T12:00:00Z",
      last_model_catalog_refresh_at: "2026-08-03T12:10:00Z",
      last_error_code: "rate_limited",
      last_error_message: "The AI provider rate limit was reached.",
    },
  ]);
  renderPage();

  expect(await screen.findByText("2026-08-03T12:00:00Z")).toBeInTheDocument();
  expect(screen.getByText("2026-08-03T12:10:00Z")).toBeInTheDocument();
  expect(screen.getByText(/rate_limited/)).toBeInTheDocument();
});

it("ignores a stale catalog response after switching AI tasks", async () => {
  let resolveOldCatalog: ((value: AdminAiCatalogResponse) => void) | undefined;
  const oldCatalog = new Promise<AdminAiCatalogResponse>((resolve) => { resolveOldCatalog = resolve; });
  api.getAdminAiTaskConfigs.mockResolvedValue([bodyConfig, progressConfig]);
  api.getAdminAiTaskModels.mockImplementation((task: string) => task === "body_photo_analysis"
    ? oldCatalog
    : Promise.resolve({
      refreshed_at: "2026-08-03T12:00:00Z",
      stale: false,
      items: [{
        provider: "openrouter",
        model_id: "vendor/progress-model",
        display_name: "Progress Model",
        provider_family: "vendor",
        supports_text_input: true,
        supports_image_input: false,
        supports_structured_output: true,
        context_length: 32000,
        input_price_per_token: null,
        output_price_per_token: null,
        available: true,
      }],
    }));
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Progress comparison" }));
  expect(await screen.findAllByRole("option", { name: /Progress Model/ })).toHaveLength(2);
  resolveOldCatalog?.({
    refreshed_at: "2026-08-03T11:00:00Z",
    stale: false,
    items: [{
      provider: "openrouter",
      model_id: "vendor/old-vision-model",
      display_name: "Old Vision Model",
      provider_family: "vendor",
      supports_text_input: true,
      supports_image_input: true,
      supports_structured_output: true,
      context_length: 32000,
      input_price_per_token: null,
      output_price_per_token: null,
      available: true,
    }],
  });

  await new Promise((resolve) => setTimeout(resolve, 0));
  await waitFor(() => expect(screen.queryByRole("option", { name: /Old Vision Model/ })).not.toBeInTheDocument());
});

it("does not refresh task A's catalog after switching to task B", async () => {
  let resolveRefresh: (() => void) | undefined;
  api.getAdminAiTaskConfigs.mockResolvedValue([
    { ...bodyConfig, credential: { configured: true, masked: "••••cret" } },
    progressConfig,
  ]);
  api.refreshAdminAiModels.mockReturnValue(new Promise((resolve) => { resolveRefresh = () => resolve({
    provider: "openrouter", model_count: 2, refreshed_at: "2026-08-03T12:00:00Z",
  }); }));
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Refresh models" }));
  await user.click(screen.getByRole("button", { name: "Progress comparison" }));
  await screen.findAllByRole("option", { name: /Vision Model/ });
  const callsBeforeResolve = api.getAdminAiTaskModels.mock.calls.length;
  resolveRefresh?.();
  await new Promise((resolve) => setTimeout(resolve, 0));

  expect(api.getAdminAiTaskModels).toHaveBeenCalledTimes(callsBeforeResolve);
  expect(screen.queryByText("Model catalog refreshed")).not.toBeInTheDocument();
});

it("does not show stale connection or save results after switching tasks", async () => {
  let resolveConnection: ((value: { ok: boolean; checked_at: string; model_count: number; error_code: null; safe_error_message: null }) => void) | undefined;
  let resolveSave: ((value: AdminAiTaskConfig) => void) | undefined;
  api.getAdminAiTaskConfigs.mockResolvedValue([bodyConfig, progressConfig]);
  api.testAdminAiProvider.mockReturnValue(new Promise((resolve) => { resolveConnection = resolve; }));
  api.saveAdminAiTaskConfig.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Test connection" }));
  await user.click(screen.getByRole("button", { name: "Progress comparison" }));
  resolveConnection?.({ ok: true, checked_at: "2026-08-03T12:00:00Z", model_count: 2, error_code: null, safe_error_message: null });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.queryByText("Connection successful")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Body-photo analysis" }));
  await user.click(screen.getByRole("button", { name: "Save" }));
  await user.click(screen.getByRole("button", { name: "Progress comparison" }));
  resolveSave?.({ ...bodyConfig, enabled: true });
  await new Promise((resolve) => setTimeout(resolve, 0));

  expect(screen.queryByText("Settings saved")).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Progress comparison" })).toBeInTheDocument();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminAiSettingsPage />
    </MemoryRouter>,
  );
}
