import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";

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

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
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
  await user.click(screen.getByRole("button", { name: "Copy code" }));
  expect(await screen.findByText("Code copied")).toBeInTheDocument();
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

it("keeps the Antigravity browser link visible while waiting for its authorization code", async () => {
  const antigravitySession: AdminAiAgentAuthSession = {
    ...waitingForUser,
    agent: "antigravity",
    verification_url: "https://accounts.google.com/o/oauth2/v2/auth?state=opaque",
    user_code: null,
    status: "waiting_for_input",
    input_label: "authorization code",
  };
  api.startAdminAiAgentAuth.mockResolvedValue(antigravitySession);

  render(<AgentAuthDialog agent="antigravity" onClose={vi.fn()} onAuthenticated={vi.fn()} />);

  expect(await screen.findByText(antigravitySession.verification_url!)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open authentication page" })).toBeInTheDocument();
  expect(screen.getByLabelText("Authorization code")).toBeInTheDocument();
});

it("polls until authenticated, notifies once, and stops at the terminal state", async () => {
  vi.useFakeTimers();
  const onAuthenticated = vi.fn();
  api.getAdminAiAgentAuthSession.mockResolvedValue({ ...waitingForUser, status: "authenticated", verification_url: null, user_code: null });
  render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={onAuthenticated} />);

  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByText("Waiting for browser sign-in")).toBeInTheDocument();
  await act(async () => {
    vi.advanceTimersByTime(2_000);
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByText("Authenticated")).toBeInTheDocument();
  expect(onAuthenticated).toHaveBeenCalledTimes(1);
  await act(async () => {
    vi.advanceTimersByTime(10_000);
    await Promise.resolve();
  });
  expect(api.getAdminAiAgentAuthSession).toHaveBeenCalledTimes(1);
});

it("ignores a stale poll response after a newer input response", async () => {
  let resolvePoll: ((value: AdminAiAgentAuthSession) => void) | undefined;
  const pollResponse = new Promise<AdminAiAgentAuthSession>((resolve) => { resolvePoll = resolve; });
  const waitingForInput: AdminAiAgentAuthSession = {
    ...waitingForUser,
    status: "waiting_for_input",
    verification_url: null,
    user_code: null,
    input_label: "authorization code",
  };
  api.startAdminAiAgentAuth.mockResolvedValue(waitingForInput);
  api.getAdminAiAgentAuthSession.mockReturnValue(pollResponse);
  api.submitAdminAiAgentAuthInput.mockResolvedValue({ ...waitingForInput, status: "authenticated" });
  vi.useFakeTimers();
  render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByLabelText("Authorization code")).toBeInTheDocument();

  await act(async () => {
    vi.advanceTimersByTime(2_000);
    await Promise.resolve();
  });
  const input = screen.getByLabelText("Authorization code");
  await act(async () => {
    fireEvent.change(input, { target: { value: "AUTH-CODE" } });
    fireEvent.submit(input.closest("form")!);
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByText("Authenticated")).toBeInTheDocument();
  resolvePoll?.(waitingForInput);
  await act(async () => { await Promise.resolve(); });
  expect(screen.getByText("Authenticated")).toBeInTheDocument();
});

it("cancels active auth on unmount and never polls after cleanup", async () => {
  vi.useFakeTimers();
  const view = render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByText("Waiting for browser sign-in")).toBeInTheDocument();
  view.unmount();
  expect(api.cancelAdminAiAgentAuthSession).toHaveBeenCalledWith("session-1");
  await act(async () => {
    vi.advanceTimersByTime(10_000);
    await Promise.resolve();
  });
  expect(api.getAdminAiAgentAuthSession).not.toHaveBeenCalled();
});

it("shows a translated safe error instead of a downstream message", async () => {
  api.startAdminAiAgentAuth.mockRejectedValue(
    new ApiError(503, "raw downstream token or stderr", null, "auth_unavailable"),
  );
  render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Authentication is temporarily unavailable.");
  expect(alert).not.toHaveTextContent("raw downstream token or stderr");
});

it("does not render or open a verification URL outside the agent allowlist", async () => {
  api.startAdminAiAgentAuth.mockResolvedValue({
    ...waitingForUser,
    verification_url: "https://evil.example/login?token=secret",
  });
  render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);

  await screen.findByText("Waiting for browser sign-in");
  expect(screen.queryByText("https://evil.example/login?token=secret")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Open authentication page" })).not.toBeInTheDocument();
});

it("deletes the active session before closing on explicit cancel", async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<AgentAuthDialog agent="codex" onClose={onClose} onAuthenticated={vi.fn()} />);

  await screen.findByText("Waiting for browser sign-in");
  await user.click(screen.getByRole("button", { name: "Cancel authentication" }));
  await waitFor(() => expect(api.cancelAdminAiAgentAuthSession).toHaveBeenCalledWith("session-1"));
  expect(onClose).toHaveBeenCalledTimes(1);
});

it("cancels the old session and starts a fresh run when the agent changes", async () => {
  api.startAdminAiAgentAuth.mockResolvedValueOnce(waitingForUser).mockResolvedValueOnce({
    ...waitingForUser,
    agent: "claude",
    verification_url: "https://claude.com/login?test=1",
  });
  const view = render(<AgentAuthDialog agent="codex" onClose={vi.fn()} onAuthenticated={vi.fn()} />);
  await screen.findByText("Waiting for browser sign-in");

  view.rerender(<AgentAuthDialog agent="claude" onClose={vi.fn()} onAuthenticated={vi.fn()} />);
  await waitFor(() => expect(api.startAdminAiAgentAuth).toHaveBeenLastCalledWith("claude"));
  expect(api.cancelAdminAiAgentAuthSession).toHaveBeenCalledWith("session-1");
});
