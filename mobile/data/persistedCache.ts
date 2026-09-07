import {
  dehydrate,
  hydrate,
  type DehydratedState,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";

import type { OpenedUserEncryptedDatabase } from "./encryptedUserDatabase";

const QUERY_CACHE_TABLE = '"__fitician_query_cache"';
const ONE_DAY_MILLISECONDS = 86_400_000;

export type PersistedCachePolicy = {
  readonly name: string;
  readonly queryKeyPrefix: readonly unknown[];
  readonly maxAgeMilliseconds: number;
};

export const persistedCachePolicies = {
  workoutPlans: {
    name: "workout-plans",
    queryKeyPrefix: ["workouts", "plan"],
    maxAgeMilliseconds: ONE_DAY_MILLISECONDS,
  },
  nutritionPlans: {
    name: "nutrition-plans",
    queryKeyPrefix: ["nutrition", "plan"],
    maxAgeMilliseconds: ONE_DAY_MILLISECONDS,
  },
} as const satisfies Record<string, PersistedCachePolicy>;

const allPersistedCachePolicies = Object.values(persistedCachePolicies);

type PersistedCacheRow = {
  readonly query_hash: string;
  readonly payload: string;
  readonly saved_at: number;
  readonly expires_at: number;
};

type DehydratedQuery = DehydratedState["queries"][number];

function queryKeyMatchesPrefix(queryKey: QueryKey, prefix: readonly unknown[]): boolean {
  return prefix.every((part, index) => queryKey[index] === part);
}

export function getPersistedCachePolicy(
  queryKey: QueryKey,
  policies: readonly PersistedCachePolicy[] = allPersistedCachePolicies,
): PersistedCachePolicy | null {
  return policies.find((policy) => queryKeyMatchesPrefix(queryKey, policy.queryKeyPrefix)) ?? null;
}

function isDehydratedQuery(value: unknown): value is DehydratedQuery {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as { queryHash?: unknown; queryKey?: unknown; state?: unknown };
  return (
    typeof candidate.queryHash === "string" &&
    Array.isArray(candidate.queryKey) &&
    typeof candidate.state === "object" &&
    candidate.state !== null
  );
}

function parseRow(row: PersistedCacheRow): DehydratedQuery | null {
  try {
    const parsed: unknown = JSON.parse(row.payload);
    if (!isDehydratedQuery(parsed) || parsed.queryHash !== row.query_hash) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export interface EncryptedQueryCacheOptions {
  now?: () => number;
  policies?: readonly PersistedCachePolicy[];
}

export class EncryptedQueryCache {
  private readonly database: OpenedUserEncryptedDatabase["database"];
  private readonly now: () => number;
  private readonly policies: readonly PersistedCachePolicy[];

  constructor(database: OpenedUserEncryptedDatabase, options: EncryptedQueryCacheOptions = {}) {
    this.database = database.database;
    this.now = options.now ?? Date.now;
    this.policies = options.policies ?? allPersistedCachePolicies;
  }

  async persist(queryClient: QueryClient): Promise<void> {
    const savedAt = this.now();
    const dehydrated = dehydrate(queryClient, {
      shouldDehydrateQuery: (query) =>
        query.state.status === "success" &&
        getPersistedCachePolicy(query.queryKey, this.policies) !== null,
    });

    await this.database.withTransactionAsync(async () => {
      await this.database.runAsync(`DELETE FROM ${QUERY_CACHE_TABLE}`);
      for (const query of dehydrated.queries) {
        const policy = getPersistedCachePolicy(query.queryKey, this.policies);
        if (policy === null) {
          continue;
        }
        await this.database.runAsync(
          `INSERT OR REPLACE INTO ${QUERY_CACHE_TABLE}
            (query_hash, payload, saved_at, expires_at)
           VALUES (?, ?, ?, ?)`,
          query.queryHash,
          JSON.stringify(query),
          savedAt,
          savedAt + policy.maxAgeMilliseconds,
        );
      }
    });
  }

  async restore(queryClient: QueryClient): Promise<void> {
    const now = this.now();
    await this.database.runAsync(
      `DELETE FROM ${QUERY_CACHE_TABLE} WHERE expires_at <= ?`,
      now,
    );
    const rows = await this.database.getAllAsync<PersistedCacheRow>(
      `SELECT query_hash, payload, saved_at, expires_at
       FROM ${QUERY_CACHE_TABLE}
       WHERE expires_at > ?`,
      now,
    );
    const queries = rows.flatMap((row) => {
      if (row.expires_at <= now) {
        return [];
      }
      const query = parseRow(row);
      return query !== null && getPersistedCachePolicy(query.queryKey, this.policies) !== null
        ? [query]
        : [];
    });
    hydrate(queryClient, { queries });
  }

  async clear(): Promise<void> {
    await this.database.runAsync(`DELETE FROM ${QUERY_CACHE_TABLE}`);
  }
}
