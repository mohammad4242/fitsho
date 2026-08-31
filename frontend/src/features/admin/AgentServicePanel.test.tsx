import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { AgentServicePanel } from "./AgentServicePanel";
import type { AdminAiAgentRunnerCapability } from "./types";

const runners: AdminAiAgentRunnerCapability[] = [
  {
    agent: "antigravity",
    installed: true,
    version: "1.1.22",
    auth_state: "unknown",
    auth_mode: "browser_link",
    models: [],
  },
  {
    agent: "codex",
    installed: true,
    version: "codex-cli 0.151.0",
    auth_state: "authenticated",
    auth_mode: "browser_link",
    models: [],
  },
  {
    agent: "claude",
    installed: false,
    version: null,
    auth_state: "unauthenticated",
    auth_mode: "unknown",
    models: [],
  },
];

beforeEach(() => {
  void i18n.changeLanguage("en");
});

it("renders all agent cards, service status, and selected routing", async () => {
  const user = userEvent.setup();
  const onSelectAgent = vi.fn();
  const onAuthenticate = vi.fn();

  render(
    <AgentServicePanel
      runners={runners}
      loading={false}
      unavailable={false}
      selectedAgent="antigravity"
      selectedModelId={null}
      onSelectAgent={onSelectAgent}
      onAuthenticate={onAuthenticate}
      onTest={vi.fn()}
      testDisabled={true}
    />,
  );

  expect(screen.getByRole("heading", { name: "Agent Service" })).toBeInTheDocument();
  expect(screen.getByText("Online")).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Antigravity" })).toHaveTextContent("1.1.22");
  expect(screen.getByRole("group", { name: "Codex" })).toHaveTextContent("codex-cli 0.151.0");
  expect(screen.getByRole("group", { name: "Claude" })).toHaveTextContent("Not installed");
  expect(screen.getByText("Selected agent: Antigravity")).toBeInTheDocument();
  expect(screen.getByText("Selected model: None")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Authenticate Claude" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Authenticate Antigravity" })).toBeEnabled();

  await user.click(screen.getByRole("button", { name: "Select Codex" }));
  expect(onSelectAgent).toHaveBeenCalledWith("codex");
  await user.click(screen.getByRole("button", { name: "Re-authenticate Codex" }));
  expect(onAuthenticate).toHaveBeenCalledWith("codex");
});

it("disables authentication when a runner is explicitly manual-only", () => {
  render(
    <AgentServicePanel
      runners={[{ ...runners[0], auth_mode: "manual" }]}
      loading={false}
      unavailable={false}
      selectedAgent="antigravity"
      selectedModelId={null}
      onSelectAgent={vi.fn()}
      onAuthenticate={vi.fn()}
      onTest={vi.fn()}
      testDisabled
    />,
  );

  expect(screen.getByRole("button", { name: "Authenticate Antigravity" })).toBeDisabled();
  expect(screen.getByText("Browser authentication is unavailable for this runner.")).toBeInTheDocument();
});

it("shows unavailable status and keeps the panel compact while loading", () => {
  const { rerender } = render(
    <AgentServicePanel
      runners={[]}
      loading
      unavailable={false}
      selectedAgent={null}
      selectedModelId={null}
      onSelectAgent={vi.fn()}
      onAuthenticate={vi.fn()}
      onTest={vi.fn()}
      testDisabled
    />,
  );
  expect(screen.getByText("Checking Agent Service…")).toBeInTheDocument();

  rerender(
    <AgentServicePanel
      runners={[]}
      loading={false}
      unavailable
      selectedAgent={null}
      selectedModelId={null}
      onSelectAgent={vi.fn()}
      onAuthenticate={vi.fn()}
      onTest={vi.fn()}
      testDisabled
    />,
  );
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
});
