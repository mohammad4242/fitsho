import { afterEach, expect, it, vi } from "vitest";

import * as SecureStore from "expo-secure-store";
import { createInitialOnboardingState, transitionOnboardingState } from "@fitician/core/onboarding";

import {
  PUBLIC_ONBOARDING_DRAFT_KEY,
  SecurePublicOnboardingDraftStore,
} from "./publicOnboardingDraftStore";

const secureStore = vi.hoisted(() => ({
  deleteItemAsync: vi.fn().mockResolvedValue(undefined),
  getItemAsync: vi.fn().mockResolvedValue(null),
  setItemAsync: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("expo-secure-store", () => secureStore);

afterEach(() => vi.clearAllMocks());

it("stores a versioned onboarding state in device-secure storage", async () => {
  const store = new SecurePublicOnboardingDraftStore({ now: () => 1_000 });
  const state = transitionOnboardingState(createInitialOnboardingState(), {
    mode: "both",
    type: "select_product_mode",
  });

  await store.save(state);

  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
    PUBLIC_ONBOARDING_DRAFT_KEY,
    expect.any(String),
  );
  const payload = JSON.parse(secureStore.setItemAsync.mock.calls[0]?.[1] as string) as Record<string, unknown>;
  expect(payload).toMatchObject({ saved_at: 1_000, schema_version: 1 });
  expect(payload.state).toEqual(state);
});

it("loads a valid draft and returns its saved timestamp", async () => {
  const store = new SecurePublicOnboardingDraftStore({ now: () => 2_000 });
  const state = createInitialOnboardingState();
  secureStore.getItemAsync.mockResolvedValueOnce(JSON.stringify({
    saved_at: 1_000,
    schema_version: 1,
    state,
  }));

  await expect(store.load()).resolves.toEqual({ savedAt: 1_000, state, status: "valid" });
});

it("clears malformed and stale drafts instead of returning unsafe state", async () => {
  const store = new SecurePublicOnboardingDraftStore({ now: () => 10_000, maxAgeMilliseconds: 1_000 });

  secureStore.getItemAsync.mockResolvedValueOnce("{bad");
  await expect(store.load()).resolves.toEqual({ savedAt: 0, status: "incompatible" });

  secureStore.getItemAsync.mockResolvedValueOnce(JSON.stringify({
    saved_at: 1_000,
    schema_version: 1,
    state: createInitialOnboardingState(),
  }));
  await expect(store.load()).resolves.toEqual({ savedAt: 1_000, status: "stale" });
  expect(secureStore.deleteItemAsync).toHaveBeenCalledWith(PUBLIC_ONBOARDING_DRAFT_KEY);
});

it("supports explicit clearing", async () => {
  const store = new SecurePublicOnboardingDraftStore();

  await store.clear();

  expect(secureStore.deleteItemAsync).toHaveBeenCalledWith(PUBLIC_ONBOARDING_DRAFT_KEY);
});
