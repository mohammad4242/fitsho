import { afterEach, expect, it, vi } from "vitest";

import { createBodyPhotoFlowDraft } from "./bodyPhotoFlow";

const secureStore = vi.hoisted(() => ({
  deleteItemAsync: vi.fn().mockResolvedValue(undefined),
  getItemAsync: vi.fn().mockResolvedValue(null),
  setItemAsync: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("expo-secure-store", () => secureStore);

import { SecureBodyPhotoDraftStore } from "./bodyPhotoDraftStore";

afterEach(() => vi.clearAllMocks());

it("stores only the small resumable flow metadata in user-scoped secure storage", async () => {
  const store = new SecureBodyPhotoDraftStore();
  const draft = createBodyPhotoFlowDraft("initial_plan", "session-1");

  await store.save("member-1", draft);

  expect(secureStore.setItemAsync).toHaveBeenCalledWith(
    "fitician.body-analysis-draft.member-1",
    expect.stringContaining('"session_id":"session-1"'),
  );
  expect(secureStore.setItemAsync.mock.calls[0]?.[1]).not.toMatch(/uri|bytes|base64|pixels/i);
});

it("loads valid drafts and clears malformed storage", async () => {
  const store = new SecureBodyPhotoDraftStore();
  const draft = createBodyPhotoFlowDraft("progress_check", "session-2");
  secureStore.getItemAsync.mockResolvedValueOnce(JSON.stringify(draft));
  await expect(store.load("member-2")).resolves.toEqual(draft);

  secureStore.getItemAsync.mockResolvedValueOnce("{bad");
  await expect(store.load("member-2")).resolves.toBeNull();
  expect(secureStore.deleteItemAsync).toHaveBeenCalledWith(
    "fitician.body-analysis-draft.member-2",
  );
});

it("isolates the draft key by user and supports explicit clearing", async () => {
  const store = new SecureBodyPhotoDraftStore();
  await store.clear("member/3");

  expect(secureStore.deleteItemAsync).toHaveBeenCalledWith(
    "fitician.body-analysis-draft.member%2F3",
  );
});
