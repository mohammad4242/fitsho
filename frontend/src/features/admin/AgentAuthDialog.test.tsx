import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";

const api = vi.hoisted(() => ({
  startAdminAiAgentAuth: vi.fn(),
  getAdminAiAgentAuthSession: vi.fn(),
  submitAdminAiAgentAuthInput: vi.fn(),
  cancelAdminAiAgentAuthSession: vi.fn(),
}));

vi.mock("./api", () => api);

import { AgentAuthDialog } from "./AgentAuthDialog";
import type { AdminAiAgentAuthSession } from "./types";

const waitingForUser: AdminAiAgentAuthSession = {
  session_id: "session-1",
  agent: "codex",
  status: "waiting_for_user",
  verification_url: "https://auth.openai.com/device?test=1",
  user_code: "ABCD-EFGH",
  input_label: null,
  expires_at: "2026-08-31T12:10:00Z",
  safe_error_message: null,
};

beforeEach(() => {
  void i18n.changeLanguage("en");
  Object.values(api).forEach((mock) => mock.mockReset());
  api.startAdminAiAgentAuth.mockResolvedValue(waitingForUser);
  api.getAdminAiAgentAuthSession.mockResolvedValue(waitingForUser);
  api.submitAdminAiAgentAuthInput.mockResolvedValue(waitingForUser);
  api.cancelAdminAiAgentAuthSession.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

it("starts auth, renders safe URL and code, and opens/copies only on explicit actions", async () => {
  const user = userEvent.setup();
  const onClose = vi.fn();
  render(<AgentAuthDialog agent="codex" onClose={onClose} onAuthenticated={vi.fn()} />);

  expect(api.startAdminAiAgentAuth).toHaveBeenCalledWith("codex");
  expect(await screen.findByRole("dialog", { name: "Authenticate Codex" })).toBeInTheDocument();
  expect(screen.getByText("ABCD-EFGH")).toBeInTheDocument();
  expect(screen.getByText("https://auth.openai.com/device?test=1")).toBeInTheDocument();

  const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
  await user.click(screen.getByRole("button", { name: "Open authentication page" }));
  expect(openSpy).toHaveBeenCalledWith(
    "https://auth.openai.com/device?test=1",
    "_blank",
    "noopener,noreferrer",
  );
  await user.click(screen.getByRole("button", { name: "Copy link" }));
  expect(await screen.findByText("Link copied")).toBeInTheDocument();
  openSpy.mockRestore();
});

it("clears authorization input immediately and sends it only to the active session", async () => {
  const user = userEvent.setup();
  const waitingForInput: AdminAiAgentAuthSession = {
    ...waitingForUser,
    status: "waiting_for_input",
    verification_url: null,
    user_code: null,
    input_label: "authorization code",
  };
  api.startAdminAiAgentAuth.mockResolvedValue(waitingForInput);
  api.submitAdminAiAgentAuthInput.mockResolvedValue({ ...waitingForInput, status: "verifying" });
  render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);

  const input = await screen.findByLabelText("Authorization code");
  await user.type(input, "AUTH-CODE");
  await user.click(screen.getByRole("button", { name: "Continue" }));

  expect(input).toHaveValue("");
  await waitFor(() => expect(api.submitAdminAiAgentAuthInput).toHaveBeenCalledWith("session-1", "AUTH-CODE"));
});
