import * as SecureStore from "expo-secure-store";

import {
  parseBodyPhotoFlowDraft,
  serializeBodyPhotoFlowDraft,
  type BodyPhotoFlowDraft,
} from "./bodyPhotoFlow";

const KEY_PREFIX = "fitician.body-analysis-draft.";

export interface BodyPhotoDraftStore {
  clear(userId: string): Promise<void>;
  load(userId: string): Promise<BodyPhotoFlowDraft | null>;
  save(userId: string, draft: BodyPhotoFlowDraft): Promise<void>;
}

export class SecureBodyPhotoDraftStore implements BodyPhotoDraftStore {
  async clear(userId: string): Promise<void> {
    await SecureStore.deleteItemAsync(storageKey(userId));
  }

  async load(userId: string): Promise<BodyPhotoFlowDraft | null> {
    const key = storageKey(userId);
    const stored = await SecureStore.getItemAsync(key);
    if (stored === null) return null;
    const draft = parseBodyPhotoFlowDraft(stored);
    if (draft !== null) return draft;
    await SecureStore.deleteItemAsync(key);
    return null;
  }

  async save(userId: string, draft: BodyPhotoFlowDraft): Promise<void> {
    await SecureStore.setItemAsync(storageKey(userId), serializeBodyPhotoFlowDraft(draft));
  }
}

function storageKey(userId: string): string {
  if (
    userId.length === 0
    || userId.length > 200
    || /\p{Cc}/u.test(userId)
  ) {
    throw new TypeError("A valid user id is required for body-photo storage");
  }
  return `${KEY_PREFIX}${encodeURIComponent(userId)}`;
}
