import * as SecureStore from "expo-secure-store";

import {
  deserializeOnboardingState,
  isOnboardingState,
  ONBOARDING_DRAFT_MAX_AGE_MILLISECONDS,
  serializeOnboardingState,
  type OnboardingDraftLoadResult,
  type OnboardingState,
  type OnboardingStateStore,
} from "@fitician/core/onboarding";

export const PUBLIC_ONBOARDING_DRAFT_KEY = "fitician.public-onboarding-draft.v1";
const PUBLIC_ONBOARDING_DRAFT_SCHEMA_VERSION = 1 as const;

export type SecurePublicOnboardingDraftStoreOptions = {
  readonly maxAgeMilliseconds?: number;
  readonly now?: () => number;
};

type PublicOnboardingDraftPayload = {
  readonly saved_at: number;
  readonly schema_version: typeof PUBLIC_ONBOARDING_DRAFT_SCHEMA_VERSION;
  readonly state: OnboardingState;
};

export class SecurePublicOnboardingDraftStore implements OnboardingStateStore {
  private readonly maxAgeMilliseconds: number;
  private readonly now: () => number;

  constructor(options: SecurePublicOnboardingDraftStoreOptions = {}) {
    const maxAgeMilliseconds = options.maxAgeMilliseconds ?? ONBOARDING_DRAFT_MAX_AGE_MILLISECONDS;
    if (!Number.isFinite(maxAgeMilliseconds) || maxAgeMilliseconds <= 0) {
      throw new RangeError("Onboarding draft max age must be a positive finite number");
    }
    this.maxAgeMilliseconds = maxAgeMilliseconds;
    this.now = options.now ?? Date.now;
  }

  async save(state: OnboardingState): Promise<void> {
    serializeOnboardingState(state);
    const payload: PublicOnboardingDraftPayload = {
      saved_at: this.now(),
      schema_version: PUBLIC_ONBOARDING_DRAFT_SCHEMA_VERSION,
      state,
    };
    await SecureStore.setItemAsync(PUBLIC_ONBOARDING_DRAFT_KEY, JSON.stringify(payload));
  }

  async load(): Promise<OnboardingDraftLoadResult> {
    const stored = await SecureStore.getItemAsync(PUBLIC_ONBOARDING_DRAFT_KEY);
    if (stored === null) return { status: "missing" };

    let payload: unknown;
    try {
      payload = JSON.parse(stored);
    } catch {
      await this.clear();
      return { savedAt: 0, status: "incompatible" };
    }

    if (!isPublicOnboardingDraftPayload(payload)) {
      await this.clear();
      return { savedAt: 0, status: "incompatible" };
    }
    if (this.now() - payload.saved_at > this.maxAgeMilliseconds) {
      await this.clear();
      return { savedAt: payload.saved_at, status: "stale" };
    }

    const state = deserializeOnboardingState(JSON.stringify(payload.state));
    if (state === null) {
      await this.clear();
      return { savedAt: payload.saved_at, status: "incompatible" };
    }
    return { savedAt: payload.saved_at, state, status: "valid" };
  }

  async clear(): Promise<void> {
    await SecureStore.deleteItemAsync(PUBLIC_ONBOARDING_DRAFT_KEY);
  }
}

function isPublicOnboardingDraftPayload(value: unknown): value is PublicOnboardingDraftPayload {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const payload = value as Record<string, unknown>;
  return (
    payload.schema_version === PUBLIC_ONBOARDING_DRAFT_SCHEMA_VERSION
    && Number.isFinite(payload.saved_at)
    && (payload.saved_at as number) >= 0
    && isOnboardingState(payload.state)
  );
}
