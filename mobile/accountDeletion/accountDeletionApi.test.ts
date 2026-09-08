import { expect, it, vi } from "vitest";

import type { TransportRequest } from "@fitician/core";

import {
  createAccountDeletionApi,
  type AuthenticatedAccountDeletionRequest,
  type AccountDeletionStatusResponse,
} from "./accountDeletionApi";

const status: AccountDeletionStatusResponse = {
  cancelled_at: null,
  completed_at: null,
  grace_period_ends_at: "2026-09-15T12:00:00Z",
  reauthenticated_at: "2026-09-08T12:00:00Z",
  request_id: "request-1",
  requested_at: "2026-09-08T12:00:00Z",
  status: "pending",
};

it("uses the shared authenticated deletion lifecycle endpoints", async () => {
  const requests: TransportRequest[] = [];
  const request = vi.fn(async (input: TransportRequest): Promise<unknown> => {
    requests.push(input);
    return status;
  });
  const api = createAccountDeletionApi(request as unknown as AuthenticatedAccountDeletionRequest);

  await expect(api.getStatus()).resolves.toEqual(status);
  await expect(api.requestDeletion("DELETE", "password")).resolves.toEqual(status);
  await expect(api.requestDeletion("DELETE")).resolves.toEqual(status);
  await expect(api.cancelDeletion()).resolves.toEqual(status);

  expect(requests).toEqual([
    { method: "GET", path: "/api/v1/account-deletion" },
    {
      body: { confirmation: "DELETE", password: "password" },
      method: "POST",
      path: "/api/v1/account-deletion",
    },
    {
      body: { confirmation: "DELETE" },
      method: "POST",
      path: "/api/v1/account-deletion",
    },
    {
      body: { confirmation: "CANCEL" },
      method: "POST",
      path: "/api/v1/account-deletion/cancel",
    },
  ]);
});
