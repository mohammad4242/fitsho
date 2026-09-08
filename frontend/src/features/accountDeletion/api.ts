import { request } from "../../shared/apiClient";

export type AccountDeletionStatus = "none" | "pending" | "cancelled" | "completed";

export type AccountDeletionStatusResponse = {
  status: AccountDeletionStatus;
  request_id: string | null;
  requested_at: string | null;
  reauthenticated_at: string | null;
  grace_period_ends_at: string | null;
  cancelled_at: string | null;
  completed_at: string | null;
};

export function getAccountDeletionStatus(): Promise<AccountDeletionStatusResponse> {
  return request<AccountDeletionStatusResponse>("/api/v1/account-deletion");
}

export function requestAccountDeletion(
  password: string | undefined,
): Promise<AccountDeletionStatusResponse> {
  return request<AccountDeletionStatusResponse>("/api/v1/account-deletion", {
    method: "POST",
    body: JSON.stringify({
      confirmation: "DELETE",
      ...(password === undefined ? {} : { password }),
    }),
  });
}

export function cancelAccountDeletion(): Promise<AccountDeletionStatusResponse> {
  return request<AccountDeletionStatusResponse>("/api/v1/account-deletion/cancel", {
    method: "POST",
    body: JSON.stringify({ confirmation: "CANCEL" }),
  });
}
