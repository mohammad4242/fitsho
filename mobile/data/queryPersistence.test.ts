import { afterEach, expect, it, vi } from "vitest";
import { QueryClient } from "@tanstack/react-query";

import type { OpenedUserEncryptedDatabase } from "./encryptedUserDatabase";
import { UserQueryCachePersistence } from "./queryPersistence";

function openedDatabase(userId: string) {
  return {
    database: { closeAsync: vi.fn().mockResolvedValue(undefined) },
    databaseName: `fitician-${userId}.db`,
    keyName: `fitician-${userId}`,
    userId,
  } as unknown as OpenedUserEncryptedDatabase;
}

afterEach(() => vi.restoreAllMocks());

it("restores and persists each user's allowlisted query cache without crossing users", async () => {
  const queryClient = new QueryClient();
  const databases = [openedDatabase("member-1"), openedDatabase("member-2")];
  const caches = databases.map(() => ({
    persist: vi.fn().mockResolvedValue(undefined),
    restore: vi.fn().mockResolvedValue(undefined),
  }));
  const openDatabase = vi.fn()
    .mockResolvedValueOnce(databases[0])
    .mockResolvedValueOnce(databases[1]);
  const persistence = new UserQueryCachePersistence({
    createCache: (database) => databases[0]!.userId === database.userId ? caches[0]! : caches[1]!,
    openDatabase,
  });

  await persistence.setUser("member-1", queryClient);
  expect(caches[0]!.restore).toHaveBeenCalledWith(queryClient);

  queryClient.setQueryData(["workouts", "plan", "active"], { status: "active" });
  await persistence.flush();
  expect(caches[0]!.persist).toHaveBeenCalledWith(queryClient);
  const firstUserPersistCount = caches[0]!.persist.mock.calls.length;

  await persistence.setUser("member-2", queryClient);
  expect(queryClient.getQueryData(["workouts", "plan", "active"])).toBeUndefined();
  expect(databases[0]!.database.closeAsync).toHaveBeenCalledOnce();
  expect(caches[1]!.restore).toHaveBeenCalledWith(queryClient);

  queryClient.setQueryData(["workouts", "plan", "active"], { status: "pending_review" });
  await persistence.flush();
  expect(caches[1]!.persist).toHaveBeenCalledWith(queryClient);
  expect(caches[0]!.persist).toHaveBeenCalledTimes(firstUserPersistCount);

  await persistence.dispose(queryClient);
  expect(databases[1]!.database.closeAsync).toHaveBeenCalledOnce();
  expect(openDatabase).toHaveBeenCalledWith("member-1");
  expect(openDatabase).toHaveBeenCalledWith("member-2");
});

it("clears memory without opening encrypted storage for signed-out users", async () => {
  const queryClient = new QueryClient();
  const openDatabase = vi.fn();
  queryClient.setQueryData(["workouts", "plan", "active"], { status: "active" });
  const persistence = new UserQueryCachePersistence({ openDatabase });

  await persistence.setUser(null, queryClient);

  expect(queryClient.getQueryData(["workouts", "plan", "active"])).toBeUndefined();
  expect(openDatabase).not.toHaveBeenCalled();
});

it("restores allowlisted state through a fresh persistence instance after process death", async () => {
  const persisted = new Map<string, unknown>();
  const queryClientBeforeDeath = new QueryClient();
  const databaseBeforeDeath = openedDatabase("member-1");
  const databaseAfterRestart = openedDatabase("member-1");
  const cacheBeforeDeath = {
    persist: vi.fn(async (client: QueryClient) => {
      persisted.set("workout-plan", client.getQueryData(["workouts", "plan", "active"]));
    }),
    restore: vi.fn(async (client: QueryClient) => {
      const value = persisted.get("workout-plan");
      if (value !== undefined) client.setQueryData(["workouts", "plan", "active"], value);
    }),
  };
  const cacheAfterRestart = {
    persist: vi.fn().mockResolvedValue(undefined),
    restore: vi.fn(async (client: QueryClient) => {
      const value = persisted.get("workout-plan");
      if (value !== undefined) client.setQueryData(["workouts", "plan", "active"], value);
    }),
  };

  const firstPersistence = new UserQueryCachePersistence({
    createCache: () => cacheBeforeDeath,
    openDatabase: async () => databaseBeforeDeath,
  });
  await firstPersistence.setUser("member-1", queryClientBeforeDeath);
  queryClientBeforeDeath.setQueryData(["workouts", "plan", "active"], { status: "active" });
  await firstPersistence.flush();
  await firstPersistence.dispose(queryClientBeforeDeath);

  const queryClientAfterRestart = new QueryClient();
  const restartedPersistence = new UserQueryCachePersistence({
    createCache: () => cacheAfterRestart,
    openDatabase: async () => databaseAfterRestart,
  });
  await restartedPersistence.setUser("member-1", queryClientAfterRestart);

  expect(queryClientAfterRestart.getQueryData(["workouts", "plan", "active"])).toEqual({
    status: "active",
  });
  expect(cacheAfterRestart.restore).toHaveBeenCalledWith(queryClientAfterRestart);

  await restartedPersistence.dispose(queryClientAfterRestart);
});
