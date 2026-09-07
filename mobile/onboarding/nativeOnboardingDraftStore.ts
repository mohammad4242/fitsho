import {
  deserializeOnboardingState,
  isOnboardingState,
  ONBOARDING_DRAFT_MAX_AGE_MILLISECONDS,
  serializeOnboardingState,
  type OnboardingDraftLoadResult,
  type OnboardingState,
  type OnboardingStateStore,
} from "@fitician/core/onboarding";

import type { OpenedUserEncryptedDatabase } from "../data/encryptedUserDatabase";

const DRAFT_TABLE = '"__fitician_onboarding_draft"';
const DRAFT_KEY = "current";
const DRAFT_SCHEMA = `
  CREATE TABLE IF NOT EXISTS ${DRAFT_TABLE} (
    draft_key TEXT PRIMARY KEY NOT NULL,
    schema_version INTEGER NOT NULL,
    mode TEXT,
    revision INTEGER NOT NULL,
    payload TEXT NOT NULL,
    saved_at INTEGER NOT NULL
  );
`;

type OnboardingDraftRow = {
  readonly draft_key: string;
  readonly schema_version: number;
  readonly mode: string | null;
  readonly revision: number;
  readonly payload: string;
  readonly saved_at: number;
};

export type NativeOnboardingDraftStoreOptions = {
  readonly now?: () => number;
  readonly maxAgeMilliseconds?: number;
};

export class NativeOnboardingDraftStore implements OnboardingStateStore {
  private readonly database: OpenedUserEncryptedDatabase["database"];
  private readonly now: () => number;
  private readonly maxAgeMilliseconds: number;

  constructor(
    openedDatabase: OpenedUserEncryptedDatabase,
    options: NativeOnboardingDraftStoreOptions = {},
  ) {
    const maxAgeMilliseconds = options.maxAgeMilliseconds ?? ONBOARDING_DRAFT_MAX_AGE_MILLISECONDS;
    if (!Number.isFinite(maxAgeMilliseconds) || maxAgeMilliseconds <= 0) {
      throw new RangeError("Onboarding draft max age must be a positive finite number");
    }
    this.database = openedDatabase.database;
    this.now = options.now ?? Date.now;
    this.maxAgeMilliseconds = maxAgeMilliseconds;
  }

  async save(state: OnboardingState): Promise<void> {
    const payload = serializeOnboardingState(state);
    await this.ensureSchema();
    await this.database.withTransactionAsync(async () => {
      await this.database.runAsync(
        `INSERT OR REPLACE INTO ${DRAFT_TABLE}
          (draft_key, schema_version, mode, revision, payload, saved_at)
         VALUES (?, ?, ?, ?, ?, ?)`,
        DRAFT_KEY,
        state.schema_version,
        state.mode,
        state.revision,
        payload,
        this.now(),
      );
    });
  }

  async load(): Promise<OnboardingDraftLoadResult> {
    await this.ensureSchema();
    const row = await this.database.getFirstAsync<OnboardingDraftRow>(
      `SELECT draft_key, schema_version, mode, revision, payload, saved_at
       FROM ${DRAFT_TABLE}
       WHERE draft_key = ?`,
      DRAFT_KEY,
    );
    if (row === null) return { status: "missing" };

    if (!Number.isFinite(row.saved_at) || row.saved_at < 0) {
      await this.deleteCurrent();
      return { status: "incompatible", savedAt: 0 };
    }
    if (this.now() - row.saved_at > this.maxAgeMilliseconds) {
      await this.deleteCurrent();
      return { status: "stale", savedAt: row.saved_at };
    }

    const state = deserializeOnboardingState(row.payload);
    if (
      state === null
      || !isOnboardingState(state)
      || row.draft_key !== DRAFT_KEY
      || row.schema_version !== state.schema_version
      || row.mode !== state.mode
      || row.revision !== state.revision
    ) {
      await this.deleteCurrent();
      return { status: "incompatible", savedAt: row.saved_at };
    }
    return { status: "valid", state, savedAt: row.saved_at };
  }

  async clear(): Promise<void> {
    await this.ensureSchema();
    await this.deleteCurrent();
  }

  private async ensureSchema(): Promise<void> {
    await this.database.execAsync(DRAFT_SCHEMA);
  }

  private async deleteCurrent(): Promise<void> {
    await this.database.runAsync(`DELETE FROM ${DRAFT_TABLE} WHERE draft_key = ?`, DRAFT_KEY);
  }
}
