import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "./api";
import { AuthProvider, useAuth } from "./AuthContext";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const { user, loading, startupError, login } = useAuth();
  return (
    <div>
      <span>
        {loading ? "loading" : startupError ? "startup-error" : (user?.email ?? "guest")}
      </span>
      <button
        type="button"
        onClick={() => login({ email: "member@example.com", password: "password" })}
      >
        login
      </button>
    </div>
  );
}

it("loads the current user on startup", async () => {
  vi.spyOn(api, "getCurrentUser").mockResolvedValue({
    id: "1",
    email: "user@example.com",
    created_at: "2026-07-24T00:00:00Z",
  });

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

  expect(screen.getByText("loading")).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getByText("user@example.com")).toBeInTheDocument(),
  );
});

it("exposes a retryable startup error instead of treating an outage as a guest", async () => {
  vi.spyOn(api, "getCurrentUser").mockRejectedValue(new Error("offline"));

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );

  expect(await screen.findByText("startup-error")).toBeInTheDocument();
  expect(screen.queryByText("guest")).not.toBeInTheDocument();
});

it("ignores a stale startup response after a successful login", async () => {
  let resolveCurrentUser: (user: null) => void = () => undefined;
  vi.spyOn(api, "getCurrentUser").mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveCurrentUser = resolve;
      }),
  );
  vi.spyOn(api, "login").mockResolvedValue({
    id: "2",
    email: "member@example.com",
    created_at: "2026-07-24T00:00:00Z",
  });
  const user = userEvent.setup();

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "login" }));
  expect(await screen.findByText("member@example.com")).toBeInTheDocument();

  await act(async () => resolveCurrentUser(null));

  expect(screen.getByText("member@example.com")).toBeInTheDocument();
});
