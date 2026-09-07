import { getRandomBytesAsync } from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import {
  deleteDatabaseAsync,
  openDatabaseAsync,
  type SQLiteDatabase,
} from "expo-sqlite";

const ENCRYPTION_KEY_BYTES = 32;
const CACHE_SCHEMA = `
  CREATE TABLE IF NOT EXISTS "__fitician_cache_schema" (
    schema_version INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS "__fitician_query_cache" (
    query_hash TEXT PRIMARY KEY NOT NULL,
    payload TEXT NOT NULL,
    saved_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
  );
`;

export type OpenedUserEncryptedDatabase = {
  readonly userId: string;
  readonly databaseName: string;
  readonly keyName: string;
  readonly database: SQLiteDatabase;
};

function validateUserId(userId: string): void {
  if (userId.length === 0 || /[\u0000-\u001f\u007f]/u.test(userId)) {
    throw new TypeError("A valid user id is required for encrypted storage");
  }
}

function encodedUserId(userId: string): string {
  validateUserId(userId);
  return encodeURIComponent(userId);
}

export function getUserDatabaseName(userId: string): string {
  return `fitician-user-cache-${encodedUserId(userId)}.db`;
}

export function getUserDatabaseKeyName(userId: string): string {
  return `fitician.sqlcipher-key.${encodedUserId(userId)}`;
}

function sqlStringLiteral(value: string): string {
  return value.replaceAll("'", "''");
}

async function createEncryptionKey(): Promise<string> {
  const bytes = await getRandomBytesAsync(ENCRYPTION_KEY_BYTES);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function openUserEncryptedDatabase(
  userId: string,
): Promise<OpenedUserEncryptedDatabase> {
  const databaseName = getUserDatabaseName(userId);
  const keyName = getUserDatabaseKeyName(userId);
  const storedKey = await SecureStore.getItemAsync(keyName);
  const encryptionKey = storedKey ?? (await createEncryptionKey());
  const database = await openDatabaseAsync(databaseName);

  try {
    await database.execAsync(`PRAGMA key = '${sqlStringLiteral(encryptionKey)}';`);
    await database.execAsync(CACHE_SCHEMA);
    if (storedKey === null) {
      await SecureStore.setItemAsync(keyName, encryptionKey);
    }
  } catch (error) {
    await database.closeAsync().catch(() => undefined);
    throw new Error("Unable to open encrypted user cache", { cause: error });
  }

  return { database, databaseName, keyName, userId };
}

export async function deleteUserEncryptedDatabase(
  userId: string,
  database?: SQLiteDatabase,
): Promise<void> {
  const databaseName = getUserDatabaseName(userId);
  const keyName = getUserDatabaseKeyName(userId);
  await database?.closeAsync();
  await deleteDatabaseAsync(databaseName);
  await SecureStore.deleteItemAsync(keyName);
}
