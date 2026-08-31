import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";

const api = vi.hoisted(() => ({
  getAdminAiTaskConfigs: vi.fn(),
  getAdminAiTaskModels: vi.fn(),
  getAdminAiAgentServiceCapabilities: vi.fn(),
  saveAdminAiTaskConfig: vi.fn(),
  testAdminAiProvider: vi.fn(),
  testAdminAiAgentService: vi.fn(),
  refreshAdminAiModels: vi.fn(),
}));

vi.mock("./api", () => api);
vi.mock("../../shared/AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => null,
}));
vi.mock("../../shared/MemberHeaderMedia", () => ({
  MemberHeaderMedia: () => null,
}));

import { AdminAiSettingsPage } from "./AdminAiSettingsPage";
import type { AdminAiCatalogResponse, AdminAiTaskConfig } from "./types";

const bodyConfig: AdminAiTaskConfig = {
  task_type: "body_photo_analysis",
  provider: "openrouter",
  execution_backend: "api",
  agent_name: null,
  agent_model_id: null,
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
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({ runners: [] });
});

it("shows the settings load error instead of staying on the loading state", async () => {
  api.getAdminAiTaskConfigs.mockRejectedValue(new ApiError(500, "Request failed"));
  renderPage();

  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load AI settings.");
  expect(screen.queryByText("Loading AI settings…")).not.toBeInTheDocument();
});

it("shows task-specific vision models and capability details", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("combobox", { name: "Primary model" }));
  expect(await screen.findAllByRole("option", { name: /Vision Model/ })).toHaveLength(1);
  await user.click(screen.getByRole("option", { name: /Vision Model/ }));
  expect(screen.getByText(/Image input/)).toBeInTheDocument();
  expect(screen.getByText(/Structured output/)).toBeInTheDocument();
});

it("requires explicit credential replacement and saves task settings", async () => {
  api.saveAdminAiTaskConfig.mockResolvedValue({
    ...bodyConfig,
    primary_model_id: "vendor/vision-model",
    credential: { configured: true, masked: "********cret" },
  });
  const user = userEvent.setup();
  renderPage();

  await user.type(await screen.findByLabelText("API key"), "sk-openrouter-secret");
  await user.click(screen.getByRole("combobox", { name: "Primary model" }));
  await user.click(screen.getByRole("option", { name: /Vision Model/ }));
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(api.saveAdminAiTaskConfig).toHaveBeenCalledWith(
    "body_photo_analysis",
    expect.objectContaining({
      api_key: "sk-openrouter-secret",
      replace_credential: true,
      primary_model_id: "vendor/vision-model",
    }),
  );
  expect(await screen.findByLabelText("API key")).toHaveAttribute(
    "placeholder",
    "********cret",
  );
});

it("tests connection and refreshes the dynamic model catalog", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([
    { ...bodyConfig, credential: { configured: true, masked: "********cret" } },
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
  const connectionMessage = await screen.findByText("Connection successful");
  expect(connectionMessage.closest(".admin-panel")).toContainElement(
    screen.getByRole("button", { name: "Test connection" }),
  );
  await user.click(screen.getByRole("button", { name: "Refresh models" }));
  expect(api.refreshAdminAiModels).toHaveBeenCalledTimes(1);
  expect(api.getAdminAiTaskModels).toHaveBeenCalledTimes(2);
});

it("shows the provider refresh error beside the provider controls", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([
    { ...bodyConfig, credential: { configured: true, masked: "********cret" } },
  ]);
  api.refreshAdminAiModels.mockRejectedValue(
    new ApiError(502, "The AI provider is temporarily unreachable."),
  );
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Refresh models" }));

  const providerError = await screen.findByRole("alert");
  expect(providerError).toHaveTextContent("The AI provider is temporarily unreachable.");
  expect(providerError.closest(".admin-panel")).toContainElement(
    screen.getByRole("button", { name: "Refresh models" }),
  );
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

it("opens a concise guide for an advanced task setting", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("About Temperature"));
  expect(screen.getByText(/0.1–0.3/)).toBeInTheDocument();
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
  await user.click(screen.getByRole("combobox", { name: "Primary model" }));
  expect(await screen.findAllByRole("option", { name: /Progress Model/ })).toHaveLength(1);
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
    { ...bodyConfig, credential: { configured: true, masked: "********cret" } },
    progressConfig,
  ]);
  api.refreshAdminAiModels.mockReturnValue(new Promise((resolve) => { resolveRefresh = () => resolve({
    provider: "openrouter", model_count: 2, refreshed_at: "2026-08-03T12:00:00Z",
  }); }));
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByRole("button", { name: "Refresh models" }));
  await user.click(screen.getByRole("button", { name: "Progress comparison" }));
  await user.click(screen.getByRole("combobox", { name: "Primary model" }));
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

it("ignores delayed task A refresh, test, and save results after an A-to-B-to-A switch", async () => {
  let resolveRefresh: (() => void) | undefined;
  let resolveConnection: ((value: { ok: boolean; checked_at: string; model_count: number; error_code: null; safe_error_message: null }) => void) | undefined;
  let resolveSave: ((value: AdminAiTaskConfig) => void) | undefined;
  api.getAdminAiTaskConfigs.mockResolvedValue([
    { ...bodyConfig, credential: { configured: true, masked: "********cret" } },
    progressConfig,
  ]);
  api.refreshAdminAiModels.mockReturnValue(new Promise((resolve) => { resolveRefresh = () => resolve({
    provider: "openrouter", model_count: 2, refreshed_at: "2026-08-03T12:00:00Z",
  }); }));
  api.testAdminAiProvider.mockReturnValue(new Promise((resolve) => { resolveConnection = resolve; }));
  api.saveAdminAiTaskConfig.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
  const user = userEvent.setup();
  renderPage();

  const bodyTab = await screen.findByRole("button", { name: "Body-photo analysis" });
  const progressTab = screen.getByRole("button", { name: "Progress comparison" });
  await user.click(screen.getByRole("button", { name: "Refresh models" }));
  await user.click(progressTab);
  await user.click(bodyTab);
  resolveRefresh?.();
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.queryByText("Model catalog refreshed")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Test connection" }));
  await user.click(progressTab);
  await user.click(bodyTab);
  resolveConnection?.({ ok: true, checked_at: "2026-08-03T12:00:00Z", model_count: 2, error_code: null, safe_error_message: null });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.queryByText("Connection successful")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Save" }));
  await user.click(progressTab);
  await user.click(bodyTab);
  resolveSave?.({ ...bodyConfig, enabled: true });
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(screen.queryByText("Settings saved")).not.toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Enabled" })).not.toBeChecked();
});

it("switches to Agent Service, loads capabilities, and filters body models", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([{ ...bodyConfig, credential: { configured: true, masked: "********cret" } }]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({
    runners: [{
      agent: "antigravity",
      installed: true,
      version: "1.1.22",
      auth_state: "authenticated",
      models: [
        { model_id: "vision-structured", supports_text_input: true, supports_image_input: true, supports_structured_output: true },
        { model_id: "image-only", supports_text_input: true, supports_image_input: true, supports_structured_output: false },
      ],
    }],
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  expect(await screen.findByText("Agent Service status")).toBeInTheDocument();
  expect(api.getAdminAiAgentServiceCapabilities).toHaveBeenCalledTimes(1);
  await user.click(screen.getByRole("combobox", { name: "Model" }));
  expect(await screen.findByRole("option", { name: /vision-structured/ })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /image-only/ })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("API key")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Refresh models" })).not.toBeInTheDocument();
});

it("hides API-only controls and disables unsupported tuning in Agent mode", async () => {
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({ runners: [{
    agent: "antigravity", installed: true, version: "1.1.22", auth_state: "authenticated",
    models: [{ model_id: "vision-structured", supports_text_input: true, supports_image_input: true, supports_structured_output: true }],
  }] });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  expect(screen.queryByLabelText("Cost ceiling per request")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Provider-routing restrictions")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Temperature")).toBeDisabled();
  expect(screen.getByLabelText("Maximum output tokens")).toBeDisabled();
  expect(screen.getByText("Temperature and maximum output controls are managed by the selected CLI.")).toBeInTheDocument();
});

it("filters Agent Service models for workout text and structured output", async () => {
  const workoutConfig: AdminAiTaskConfig = {
    ...bodyConfig,
    task_type: "workout_plan_generation",
  };
  api.getAdminAiTaskConfigs.mockResolvedValue([workoutConfig]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({
    runners: [{
      agent: "codex",
      installed: true,
      version: "0.151.0",
      auth_state: "authenticated",
      models: [
        { model_id: "text-structured", supports_text_input: true, supports_image_input: false, supports_structured_output: true },
        { model_id: "text-only", supports_text_input: true, supports_image_input: false, supports_structured_output: false },
        { model_id: "image-structured", supports_text_input: false, supports_image_input: true, supports_structured_output: true },
      ],
    }],
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  await user.click(screen.getByRole("combobox", { name: "Agent" }));
  await user.click(screen.getByRole("option", { name: "Codex" }));
  await user.click(screen.getByRole("combobox", { name: "Model" }));
  expect(await screen.findByRole("option", { name: /text-structured/ })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /text-only/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /image-structured/ })).not.toBeInTheDocument();
});

it("filters Agent Service food-photo models by image and structured capabilities", async () => {
  const foodConfig: AdminAiTaskConfig = {
    ...bodyConfig,
    task_type: "food_photo_estimation",
  };
  api.getAdminAiTaskConfigs.mockResolvedValue([foodConfig]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({
    runners: [{
      agent: "claude",
      installed: true,
      version: "2.1.220",
      auth_state: "authenticated",
      models: [
        { model_id: "food-vision", supports_text_input: true, supports_image_input: true, supports_structured_output: true },
        { model_id: "food-image-only", supports_text_input: true, supports_image_input: true, supports_structured_output: false },
      ],
    }],
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  await user.click(screen.getByRole("combobox", { name: "Model" }));
  expect(await screen.findByRole("option", { name: /food-vision/ })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /food-image-only/ })).not.toBeInTheDocument();
});

it("tests the selected Agent and shows its safe failure without leaking details", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([{ ...bodyConfig, credential: { configured: true, masked: "********cret" } }]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({ runners: [{
    agent: "antigravity", installed: true, version: "1.1.22", auth_state: "authenticated",
    models: [{ model_id: "vision-structured", supports_text_input: true, supports_image_input: true, supports_structured_output: true }],
  }] });
  api.testAdminAiAgentService.mockResolvedValue({
    ok: false,
    agent: "antigravity",
    model_id: "vision-structured",
    checked_at: "2026-08-03T12:00:00Z",
    duration_seconds: null,
    error_code: "agent_unavailable",
    safe_error_message: "The selected Agent Service runner is unavailable.",
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  await user.click(screen.getByRole("combobox", { name: "Model" }));
  await user.click(screen.getByRole("option", { name: /vision-structured/ }));
  await user.click(screen.getByRole("button", { name: "Test Agent" }));
  expect(api.testAdminAiAgentService).toHaveBeenCalledWith("antigravity", "vision-structured");
  expect(await screen.findByRole("alert")).toHaveTextContent("The selected Agent Service runner is unavailable.");
  expect(screen.queryByText(/agent-service-test-token|Bearer/i)).not.toBeInTheDocument();
});

it("saves Agent Service routing without sending or replacing the stored API key", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([{
    ...bodyConfig,
    credential: { configured: true, masked: "********cret" },
  }]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({ runners: [{
    agent: "antigravity", installed: true, version: "1.1.22", auth_state: "authenticated",
    models: [{ model_id: "vision-structured", supports_text_input: true, supports_image_input: true, supports_structured_output: true }],
  }] });
  api.saveAdminAiTaskConfig.mockResolvedValue({
    ...bodyConfig,
    execution_backend: "agent_service",
    agent_name: "antigravity",
    agent_model_id: "vision-structured",
  });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("Agent Service"));
  await user.click(screen.getByRole("combobox", { name: "Model" }));
  await user.click(screen.getByRole("option", { name: /vision-structured/ }));
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(api.saveAdminAiTaskConfig).toHaveBeenCalledWith(
    "body_photo_analysis",
    expect.objectContaining({
      execution_backend: "agent_service",
      agent_name: "antigravity",
      agent_model_id: "vision-structured",
      replace_credential: false,
    }),
  );
  expect(api.saveAdminAiTaskConfig.mock.calls[0][1]).not.toHaveProperty("api_key");
});

it("restores API controls and the stored key placeholder when switching back", async () => {
  api.getAdminAiTaskConfigs.mockResolvedValue([{
    ...bodyConfig,
    execution_backend: "agent_service",
    agent_name: "antigravity",
    agent_model_id: "vision-structured",
    credential: { configured: true, masked: "********cret" },
  }]);
  api.getAdminAiAgentServiceCapabilities.mockResolvedValue({ runners: [] });
  const user = userEvent.setup();
  renderPage();

  await user.click(await screen.findByLabelText("API"));
  expect(await screen.findByLabelText("API key")).toHaveAttribute("placeholder", "********cret");
  expect(screen.getByRole("button", { name: "Refresh models" })).toBeEnabled();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminAiSettingsPage />
    </MemoryRouter>,
  );
}
