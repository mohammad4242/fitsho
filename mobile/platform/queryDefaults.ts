import { onlineManager, type DefaultOptions } from "@tanstack/react-query";

import { ApiError } from "@fitician/core";

const RETRYABLE_API_STATUSES = new Set([408, 425, 429]);
const MAX_QUERY_RETRIES = 2;
const MAX_RETRY_DELAY_MILLISECONDS = 30_000;

export function shouldRetryMobileQuery(
  failureCount: number,
  error: unknown,
  isOnline: boolean = onlineManager.isOnline(),
): boolean {
  if (!isOnline || failureCount >= MAX_QUERY_RETRIES) {
    return false;
  }
  if (error instanceof ApiError) {
    return error.status >= 500 || RETRYABLE_API_STATUSES.has(error.status);
  }
  return true;
}

export function mobileRetryDelay(attemptIndex: number): number {
  return Math.min(1_000 * 2 ** attemptIndex, MAX_RETRY_DELAY_MILLISECONDS);
}

export const mobileQueryDefaults: DefaultOptions = {
  queries: {
    networkMode: "online",
    refetchOnReconnect: true,
    retry: (failureCount, error) => shouldRetryMobileQuery(failureCount, error),
    retryDelay: mobileRetryDelay,
  },
  mutations: {
    networkMode: "always",
    retry: false,
  },
};
