import { ApiError } from "@fitician/core";
import type { QueryObserverResult } from "@tanstack/react-query";

import type { ConnectivityStatus } from "../platform/connectivity";

export type MobileQueryResult<TData> = Pick<
  QueryObserverResult<TData, unknown>,
  "data" | "error" | "isError" | "isFetching" | "isPending" | "isStale"
>;

export type MobileStateErrorKind = "validation" | "permission" | "server";

export type MobileStateError = {
  readonly kind: MobileStateErrorKind;
  readonly message: string;
  readonly status: number | null;
  readonly code: string | null;
  readonly retryable: boolean;
};

export type MobileViewState<TData> =
  | { readonly status: "loading" }
  | { readonly status: "empty"; readonly data: TData; readonly isStale: boolean }
  | { readonly status: "ready"; readonly data: TData }
  | { readonly status: "stale"; readonly data: TData }
  | { readonly status: "offline"; readonly data?: TData; readonly isStale?: boolean }
  | {
      readonly status: "error";
      readonly error: MobileStateError;
      readonly data?: TData;
      readonly isStale?: boolean;
    };

export interface MobileViewStateOptions<TData> {
  readonly connectivityStatus?: ConnectivityStatus;
  readonly isEmpty?: (data: TData) => boolean;
}

function isNetworkFailure(error: unknown): boolean {
  if (error instanceof ApiError || error === null || typeof error !== "object") {
    return false;
  }
  const candidate = error as { readonly name?: unknown; readonly message?: unknown };
  if (candidate.name === "AbortError") {
    return false;
  }
  return (
    error instanceof TypeError ||
    (typeof candidate.message === "string" &&
      /network|offline|timeout|timed out|connection|fetch failed/i.test(candidate.message))
  );
}

function isDefaultEmpty<TData>(data: TData): boolean {
  return data === null || (Array.isArray(data) && data.length === 0);
}

export function classifyMobileStateError(error: unknown): MobileStateError {
  if (error instanceof ApiError) {
    const kind: MobileStateErrorKind =
      error.status === 400 || error.status === 409 || error.status === 422
        ? "validation"
        : error.status === 401 || error.status === 403
          ? "permission"
          : "server";
    return {
      code: error.code,
      kind,
      message: error.message,
      retryable: error.status === 408 || error.status === 425 || error.status === 429 || error.status >= 500,
      status: error.status,
    };
  }
  return {
    code: null,
    kind: "server",
    message: "Request failed",
    retryable: true,
    status: null,
  };
}

export function mobileRequestErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return "برای این عملیات دسترسی لازم وجود ندارد.";
    if (error.status === 408 || error.status === 425 || error.status === 429) {
      return "سرویس موقتاً شلوغ است؛ کمی بعد دوباره تلاش کن.";
    }
    if (error.status >= 500) return "سرویس موقتاً در دسترس نیست؛ دوباره تلاش کن.";
  }
  return fallback;
}

export function getMobileViewState<TData>(
  result: MobileQueryResult<TData>,
  options: MobileViewStateOptions<TData> = {},
): MobileViewState<TData> {
  const hasData = result.data !== undefined;
  const isOffline =
    options.connectivityStatus === "offline" || (result.isError && isNetworkFailure(result.error));

  if (isOffline) {
    return hasData
      ? { data: result.data, isStale: result.isStale, status: "offline" }
      : { status: "offline" };
  }
  if (result.isPending && !hasData) {
    return { status: "loading" };
  }
  if (result.isError) {
    return {
      ...(hasData ? { data: result.data, isStale: true } : {}),
      error: classifyMobileStateError(result.error),
      status: "error",
    };
  }
  if (!hasData) {
    return { status: "loading" };
  }

  const data = result.data as TData;
  if ((options.isEmpty ?? isDefaultEmpty)(data)) {
    return { data, isStale: result.isStale || result.isFetching, status: "empty" };
  }
  if (result.isFetching || result.isStale) {
    return { data, status: "stale" };
  }
  return { data, status: "ready" };
}
