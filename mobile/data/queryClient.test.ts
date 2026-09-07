import { expect, it } from "vitest";

import { QueryClient } from "@tanstack/react-query";

import { createMobileQueryClient } from "./queryClient";

it("creates an isolated TanStack Query client for the native app", () => {
  const first = createMobileQueryClient();
  const second = createMobileQueryClient();

  expect(first).toBeInstanceOf(QueryClient);
  expect(second).toBeInstanceOf(QueryClient);
  expect(first).not.toBe(second);
});
