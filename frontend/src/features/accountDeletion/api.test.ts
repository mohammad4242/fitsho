import { afterEach, describe, expect, it, vi } from "vitest";

import { cancelAccountDeletion, getAccountDeletionStatus, requestAccountDeletion } from "./api";

const pending = {
  status: "pending" as const,
  request_id: "018f0000-0000-7000-8000-000000000001",
  requested_at: "2026-09-08T10:00:00Z",
  reauthenticated_at: "2026-09-08T10:00:00Z",
  grace_period_ends_at: "2026-09-15T10:00:00Z",
  cancelled_at: null,
  completed_at: null,
};

afterEach(() => vi.restoreAllMocks());

describe("account deletion api", () => {
  it("reads the authenticated deletion status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(pending), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getAccountDeletionStatus()).resolves.toEqual(pending);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/account-deletion",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
  });

  it("sends the exact deletion confirmation and optional password", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(pending), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(requestAccountDeletion("long password")).resolves.toEqual(pending);
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/account-deletion",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ confirmation: "DELETE", password: "long password" }),
      }),
    );
  });

  it("cancels the pending request with the cancellation confirmation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ...pending, status: "cancelled" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await cancelAccountDeletion();

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/account-deletion/cancel",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ confirmation: "CANCEL" }),
      }),
    );
  });
});
