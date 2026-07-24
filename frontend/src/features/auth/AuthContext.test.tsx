import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import * as api from "./api";
import { AuthProvider, useAuth } from "./AuthContext";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const { user, loading } = useAuth();
  return <div>{loading ? "loading" : (user?.email ?? "guest")}</div>;
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
