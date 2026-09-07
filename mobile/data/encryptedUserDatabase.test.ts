import { afterEach, expect, it, vi } from "vitest";

import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import * as SQLite from "expo-sqlite";

import {
  deleteUserEncryptedDatabase,
  getUserDatabaseKeyName,
  getUserDatabaseName,
  openUserEncryptedDatabase,
} from "./encryptedUserDatabase";

vi.mock("expo-crypto", () => ({
  getRandomBytesAsync: vi.fn(),
}));

vi.mock("expo-secure-store", () => ({
  deleteItemAsync: vi.fn(),
  getItemAsync: vi.fn(),
  setItemAsync: vi.fn(),
}));

vi.mock("expo-sqlite", () => ({
  deleteDatabaseAsync: vi.fn(),
  openDatabaseAsync: vi.fn(),
}));

afterEach(() => vi.clearAllMocks());

function fakeDatabase() {
  return {
    closeAsync: vi.fn().mockResolvedValue(undefined),
    execAsync: vi.fn().mockResolvedValue(undefined),
  };
}

it("uses isolated database and SecureStore names for each user", () => {
  expect(getUserDatabaseName("user/one")).not.toBe(getUserDatabaseName("user/two"));
  expect(getUserDatabaseKeyName("user/one")).not.toBe(getUserDatabaseKeyName("user/two"));
  expect(getUserDatabaseName("user/one")).toContain("user%2Fone");
});

it("creates and validates a new per-user SQLCipher key before storing it", async () => {
  const database = fakeDatabase();
  vi.mocked(SecureStore.getItemAsync).mockResolvedValue(null);
  vi.mocked(Crypto.getRandomBytesAsync).mockResolvedValue(Uint8Array.from([1, 2, 3, 4]));
  vi.mocked(SQLite.openDatabaseAsync).mockResolvedValue(
    database as unknown as SQLite.SQLiteDatabase,
  );

  const opened = await openUserEncryptedDatabase("user-1");

  expect(opened.database).toBe(database);
  expect(SQLite.openDatabaseAsync).toHaveBeenCalledWith("fitician-user-cache-user-1.db");
  expect(database.execAsync).toHaveBeenCalledTimes(2);
  expect(database.execAsync.mock.calls[0][0]).toContain("PRAGMA key =");
  expect(database.execAsync.mock.calls[1][0]).toContain("CREATE TABLE IF NOT EXISTS");
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith(
    "fitician.sqlcipher-key.user-1",
    "01020304",
  );
  expect(
    (SecureStore.setItemAsync as unknown as { mock: { invocationCallOrder: number[] } }).mock
      .invocationCallOrder[0],
  ).toBeGreaterThan(database.execAsync.mock.invocationCallOrder[1]);
});

it("does not open an existing encrypted database with a missing key", async () => {
  const database = fakeDatabase();
  vi.mocked(SecureStore.getItemAsync).mockResolvedValue(null);
  vi.mocked(Crypto.getRandomBytesAsync).mockResolvedValue(Uint8Array.from([9, 8, 7, 6]));
  vi.mocked(SQLite.openDatabaseAsync).mockResolvedValue(
    database as unknown as SQLite.SQLiteDatabase,
  );
  database.execAsync.mockImplementationOnce(async () => undefined).mockRejectedValue(
    new Error("file is not a database"),
  );

  await expect(openUserEncryptedDatabase("user-1")).rejects.toThrow(
    "Unable to open encrypted user cache",
  );
  expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  expect(database.closeAsync).toHaveBeenCalledOnce();
});

it("deletes the user database before removing its SecureStore key", async () => {
  const database = fakeDatabase();
  vi.mocked(SecureStore.getItemAsync).mockResolvedValue("stored-key");
  vi.mocked(SQLite.openDatabaseAsync).mockResolvedValue(
    database as unknown as SQLite.SQLiteDatabase,
  );

  await openUserEncryptedDatabase("user-1");
  await deleteUserEncryptedDatabase(
    "user-1",
    database as unknown as SQLite.SQLiteDatabase,
  );

  expect(database.closeAsync).toHaveBeenCalledOnce();
  expect(SQLite.deleteDatabaseAsync).toHaveBeenCalledWith("fitician-user-cache-user-1.db");
  expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("fitician.sqlcipher-key.user-1");
});
