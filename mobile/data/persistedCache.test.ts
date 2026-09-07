import { expect, it, vi } from "vitest";

import { dehydrate, QueryClient } from "@tanstack/react-query";

import type { OpenedUserEncryptedDatabase } from "./encryptedUserDatabase";
import {
  EncryptedQueryCache,
  getPersistedCachePolicy,
  persistedCachePolicies,
} from "./persistedCache";

function fakeDatabase() {
  const runAsync = vi.fn().mockResolvedValue({ changes: 1, lastInsertRowId: 0 });
  const getAllAsync = vi.fn().mockResolvedValue([]);
  const withTransactionAsync = vi.fn(async (task: () => Promise<void>) => task());
  return { getAllAsync, runAsync, withTransactionAsync };
}

function openedDatabase(database: ReturnType<typeof fakeDatabase>) {
  return {
    database: database as never,
    databaseName: "fitician-user-cache-user-1.db",
    keyName: "fitician.sqlcipher-key.user-1",
    userId: "user-1",
  } as OpenedUserEncryptedDatabase;
}

it("allowlists only offline plan query prefixes with bounded expiry", () => {
  expect(getPersistedCachePolicy(["workouts", "plan", "plan-1"])).toEqual(
    persistedCachePolicies.workoutPlans,
  );
  expect(getPersistedCachePolicy(["nutrition", "plan", "plan-1"])).toEqual(
    persistedCachePolicies.nutritionPlans,
  );
  expect(getPersistedCachePolicy(["body-analysis", "session", "session-1"])).toBeNull();
  expect(getPersistedCachePolicy(["nutrition", "profile"])).toBeNull();
  expect(persistedCachePolicies.workoutPlans.maxAgeMilliseconds).toBe(86_400_000);
});

it("persists successful allowlisted queries and excludes sensitive queries", async () => {
  const queryClient = new QueryClient();
  queryClient.setQueryData(["workouts", "plan", "plan-1"], { status: "active" });
  queryClient.setQueryData(["body-analysis", "session", "session-1"], {
    measurements: { waist: 80 },
  });
  const database = fakeDatabase();
  const cache = new EncryptedQueryCache(openedDatabase(database), { now: () => 1_000 });

  await cache.persist(queryClient);

  const insert = database.runAsync.mock.calls.find(([sql]) => String(sql).includes("INSERT"));
  expect(insert).toBeDefined();
  expect(database.runAsync.mock.calls.filter(([sql]) => String(sql).includes("INSERT"))).toHaveLength(
    1,
  );
  expect(String(insert?.[2])).toContain("active");
  expect(String(insert?.[2])).not.toContain("waist");
});

it("restores unexpired allowlisted queries and removes expired rows", async () => {
  const source = new QueryClient();
  source.setQueryData(["nutrition", "plan", "plan-1"], { stale: true });
  const dehydrated = dehydrate(source);
  const query = dehydrated.queries[0];
  const database = fakeDatabase();
  database.getAllAsync.mockResolvedValue([
    {
      expires_at: 2_000,
      payload: JSON.stringify(query),
      query_hash: query.queryHash,
      saved_at: 1_000,
    },
    {
      expires_at: 999,
      payload: JSON.stringify(query),
      query_hash: query.queryHash,
      saved_at: 500,
    },
  ]);
  const target = new QueryClient();
  const cache = new EncryptedQueryCache(openedDatabase(database), { now: () => 1_500 });

  await cache.restore(target);

  expect(target.getQueryData(["nutrition", "plan", "plan-1"])).toEqual({ stale: true });
  expect(database.runAsync).toHaveBeenCalledWith(
    expect.stringContaining("expires_at <= ?"),
    1_500,
  );
});
