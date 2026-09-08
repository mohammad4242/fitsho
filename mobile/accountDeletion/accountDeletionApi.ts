import type { TransportRequest } from "@fitician/core";

export type AccountDeletionStatus = "none" | "pending" | "cancelled" | "completed";

export interface AccountDeletionStatusResponse {
  readonly cancelled_at: string | null;
  readonly completed_at: string | null;
  readonly grace_period_ends_at: string | null;
  readonly reauthenticated_at: string | null;
  readonly request_id: string | null;
  readonly requested_at: string | null;
  readonly status: AccountDeletionStatus;
}

export type AuthenticatedAccountDeletionRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface AccountDeletionApi {
  cancelDeletion(): Promise<AccountDeletionStatusResponse>;
  getStatus(): Promise<AccountDeletionStatusResponse>;
  requestDeletion(
    confirmation: "DELETE",
    password?: string,
  ): Promise<AccountDeletionStatusResponse>;
}

const accountDeletionPath = "/api/v1/account-deletion";

export function createAccountDeletionApi(
  request: AuthenticatedAccountDeletionRequest,
): AccountDeletionApi {
  return {
    cancelDeletion: () => request<AccountDeletionStatusResponse>({
      body: { confirmation: "CANCEL" },
      method: "POST",
      path: `${accountDeletionPath}/cancel`,
    }),
    getStatus: () => request<AccountDeletionStatusResponse>({
      method: "GET",
      path: accountDeletionPath,
    }),
    requestDeletion: (confirmation, password) => request<AccountDeletionStatusResponse>({
      body: password === undefined
        ? { confirmation }
        : { confirmation, password },
      method: "POST",
      path: accountDeletionPath,
    }),
  };
}
