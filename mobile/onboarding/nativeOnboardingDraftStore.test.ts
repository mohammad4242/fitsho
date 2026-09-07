import { expect, it, vi } from "vitest";

import {
  createInitialOnboardingState,
  transitionOnboardingState,
} from "@fitician/core/onboarding";

import type { OpenedUserEncryptedDatabase } from "../data/encryptedUserDatabase";
import { NativeOnboardingDraftStore } from "./nativeOnboardingDraftStore";

function state() {
  return transitionOnboardingState(createInitialOnboardingState(), {
    type: "select_product_mode",
    mode: "training",
  });
}

function fakeDatabase() {
  const execAsync = vi.fn().mockResolvedValue(undefined);
  const runAsync = vi.fn().mockResolvedValue({ changes: 1, lastInsertRowId: 0 });
  const getFirstAsync = vi.fn().mockResolvedValue(null);
  const withTransactionAsync = vi.fn(async (task: () => Promise<void>) => task());
  return { execAsync, getFirstAsync, runAsync, withTransactionAsync };
}

function openedDatabase(database: ReturnType<typeof fakeDatabase>) {
  return {
    database: database as never,
    databaseName: "fitician-user-cache-user-1.db",
    keyName: "fitician.sqlcipher-key.user-1",
    userId: "user-1",
  } as OpenedUserEncryptedDatabase;
}

it("persists one versioned onboarding draft in the encrypted user database", async () => {
  const database = fakeDatabase();
  const store = new NativeOnboardingDraftStore(openedDatabase(database), { now: () => 10_000 });

  await store.save(state());

  expect(database.execAsync).toHaveBeenCalledWith(expect.stringContaining("CREATE TABLE IF NOT EXISTS"));
  expect(database.withTransactionAsync).toHaveBeenCalledOnce();
  const insert = database.runAsync.mock.calls.find(([sql]) => String(sql).includes("INSERT OR REPLACE"));
  expect(insert).toBeDefined();
  expect(insert?.[1]).toBe("current");
  expect(insert?.[2]).toBe(1);
  expect(insert?.[3]).toBe("training");
  expect(insert?.[4]).toBe(1);
  expect(String(insert?.[5])).toContain('"step":"shared_profile"');
  expect(insert?.[6]).toBe(10_000);
});

it("restores a valid draft and rejects malformed or mismatched rows", async () => {
  const database = fakeDatabase();
  const current = state();
  database.getFirstAsync.mockResolvedValue({
    draft_key: "current",
    schema_version: 1,
    mode: "training",
    revision: current.revision,
    payload: JSON.stringify(current),
    saved_at: 9_000,
  });
  const store = new NativeOnboardingDraftStore(openedDatabase(database), { now: () => 10_000 });

  await expect(store.load()).resolves.toEqual({ status: "valid", state: current, savedAt: 9_000 });

  database.getFirstAsync.mockResolvedValue({
    draft_key: "current",
    schema_version: 1,
    mode: "nutrition",
    revision: current.revision,
    payload: JSON.stringify(current),
    saved_at: 9_000,
  });
  await expect(store.load()).resolves.toEqual({ status: "incompatible", savedAt: 9_000 });
  expect(database.runAsync).toHaveBeenCalledWith(expect.stringContaining("DELETE FROM"), "current");
});

it("rejects stale drafts and clears them before the next launch", async () => {
  const database = fakeDatabase();
  database.getFirstAsync.mockResolvedValue({
    draft_key: "current",
    schema_version: 1,
    mode: "training",
    revision: 1,
    payload: JSON.stringify(state()),
    saved_at: 1_000,
  });
  const store = new NativeOnboardingDraftStore(openedDatabase(database), {
    now: () => 10_000,
    maxAgeMilliseconds: 5_000,
  });

  await expect(store.load()).resolves.toEqual({ status: "stale", savedAt: 1_000 });
  expect(database.runAsync).toHaveBeenCalledWith(expect.stringContaining("DELETE FROM"), "current");
});

it("clears the current draft without touching other encrypted user data", async () => {
  const database = fakeDatabase();
  const store = new NativeOnboardingDraftStore(openedDatabase(database));

  await store.clear();

  expect(database.runAsync).toHaveBeenCalledWith(
    expect.stringContaining('DELETE FROM "__fitician_onboarding_draft"'),
    "current",
  );
});
