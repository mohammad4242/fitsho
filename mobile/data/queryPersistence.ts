import { QueryClient } from "@tanstack/react-query";

import type { OpenedUserEncryptedDatabase } from "./encryptedUserDatabase";
import { EncryptedQueryCache } from "./persistedCache";

export interface QueryCachePersistenceStore {
  persist(queryClient: QueryClient): Promise<void>;
  restore(queryClient: QueryClient): Promise<void>;
}

export interface UserQueryCachePersistenceOptions {
  readonly createCache?: (database: OpenedUserEncryptedDatabase) => QueryCachePersistenceStore;
  readonly openDatabase?: (userId: string) => Promise<OpenedUserEncryptedDatabase>;
}

type ActiveCache = {
  readonly database: OpenedUserEncryptedDatabase;
  readonly cache: QueryCachePersistenceStore;
  readonly generation: number;
  readonly unsubscribe: () => void;
};

export class UserQueryCachePersistence {
  private readonly createCache: (database: OpenedUserEncryptedDatabase) => QueryCachePersistenceStore;
  private readonly openDatabase: (userId: string) => Promise<OpenedUserEncryptedDatabase>;
  private active: ActiveCache | null = null;
  private generation = 0;
  private transition: Promise<void> = Promise.resolve();
  private writes: Promise<void> = Promise.resolve();

  constructor(options: UserQueryCachePersistenceOptions = {}) {
    this.createCache = options.createCache ?? ((database) => new EncryptedQueryCache(database));
    if (options.openDatabase === undefined) {
      throw new Error("An encrypted user database opener is required");
    }
    this.openDatabase = options.openDatabase;
  }

  setUser(userId: string | null, queryClient: QueryClient): Promise<void> {
    const next = this.transition.then(() => this.replaceUser(userId, queryClient));
    this.transition = next.catch(() => undefined);
    return next;
  }

  async dispose(queryClient: QueryClient): Promise<void> {
    await this.setUser(null, queryClient);
  }

  async flush(): Promise<void> {
    await this.transition;
    await this.writes;
  }

  private async replaceUser(userId: string | null, queryClient: QueryClient): Promise<void> {
    await this.stopActive();
    queryClient.clear();
    if (userId === null) return;

    const database = await this.openDatabase(userId);
    const cache = this.createCache(database);
    try {
      await cache.restore(queryClient);
    } catch (error) {
      await database.database.closeAsync().catch(() => undefined);
      throw error;
    }

    const generation = ++this.generation;
    let active: ActiveCache;
    const unsubscribe = queryClient.getQueryCache().subscribe(() => {
      this.queuePersist(active, queryClient);
    });
    active = { cache, database, generation, unsubscribe };
    this.active = active;
  }

  private queuePersist(active: ActiveCache, queryClient: QueryClient): void {
    this.writes = this.writes.then(async () => {
      if (this.active?.generation !== active.generation) return;
      try {
        await active.cache.persist(queryClient);
      } catch {
        // A cache write must not interrupt the member's online session.
      }
    });
  }

  private async stopActive(): Promise<void> {
    const active = this.active;
    this.active = null;
    if (active === null) return;
    active.unsubscribe();
    await this.writes;
    await active.database.database.closeAsync();
  }
}
