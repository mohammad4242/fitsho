import { expect, it } from "vitest";

import { ApiError } from "@fitician/core";

import { getMobileViewState, type MobileQueryResult } from "./requestState";

function result<TData>(overrides: Partial<MobileQueryResult<TData>> = {}): MobileQueryResult<TData> {
  return {
    data: undefined,
    error: null,
    isError: false,
    isFetching: false,
    isPending: true,
    isStale: false,
    ...overrides,
  };
}

it("normalizes loading, empty, ready, and stale query states", () => {
  expect(getMobileViewState(result())).toEqual({ status: "loading" });
  expect(
    getMobileViewState(result({ data: [], isPending: false }), { isEmpty: (data) => data.length === 0 }),
  ).toEqual({ data: [], isStale: false, status: "empty" });
  expect(getMobileViewState(result({ data: ["plan"], isPending: false }))).toEqual({
    data: ["plan"],
    status: "ready",
  });
  expect(
    getMobileViewState(result({ data: ["plan"], isFetching: true, isPending: false })),
  ).toEqual({ data: ["plan"], status: "stale" });
});

it("keeps offline state explicit with or without cached data", () => {
  expect(
    getMobileViewState(result(), { connectivityStatus: "offline" }),
  ).toEqual({ status: "offline" });
  expect(
    getMobileViewState(
      result({ data: ["cached"], isPending: false }),
      { connectivityStatus: "offline" },
    ),
  ).toEqual({ data: ["cached"], isStale: false, status: "offline" });
});

it("classifies validation, permission, and server failures", () => {
  expect(
    getMobileViewState(
      result({ error: new ApiError(422, "Invalid value"), isError: true, isPending: false }),
    ),
  ).toMatchObject({ status: "error", error: { kind: "validation", retryable: false, status: 422 } });
  expect(
    getMobileViewState(
      result({ error: new ApiError(403, "Forbidden"), isError: true, isPending: false }),
    ),
  ).toMatchObject({ status: "error", error: { kind: "permission", retryable: false, status: 403 } });
  expect(
    getMobileViewState(
      result({ error: new ApiError(503, "Unavailable"), isError: true, isPending: false }),
    ),
  ).toMatchObject({ status: "error", error: { kind: "server", retryable: true, status: 503 } });
});

it("maps transport failures to offline state without leaking raw errors", () => {
  const state = getMobileViewState(
    result({ error: new TypeError("Network request failed"), isError: true, isPending: false }),
  );

  expect(state).toEqual({ status: "offline" });
});
