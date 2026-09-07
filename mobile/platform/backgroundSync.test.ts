import { afterEach, expect, it, vi } from "vitest";

import * as BackgroundTask from "expo-background-task";
import * as TaskManager from "expo-task-manager";

import {
  BACKGROUND_SYNC_TASK_IDENTIFIER,
  executeBackgroundSync,
  registerBackgroundSync,
  setBackgroundSyncHandler,
  unregisterBackgroundSync,
} from "./backgroundSync";

vi.mock("expo-background-task", () => ({
  BackgroundTaskResult: { Failed: 2, Success: 1 },
  registerTaskAsync: vi.fn(),
  unregisterTaskAsync: vi.fn(),
}));

vi.mock("expo-task-manager", () => ({
  defineTask: vi.fn(),
}));

afterEach(() => {
  setBackgroundSyncHandler(null);
  vi.clearAllMocks();
});

it("defines a non-sensitive background sync task and succeeds with no pending work", async () => {
  expect(BACKGROUND_SYNC_TASK_IDENTIFIER).toBe("fitician-background-sync");
  expect(TaskManager.defineTask).toHaveBeenCalledWith(
    BACKGROUND_SYNC_TASK_IDENTIFIER,
    expect.any(Function),
  );
  await expect(executeBackgroundSync()).resolves.toBe(BackgroundTask.BackgroundTaskResult.Success);
});

it("reports handler failure and enforces Android's minimum interval", async () => {
  setBackgroundSyncHandler(async () => {
    throw new Error("sync failed");
  });

  await expect(executeBackgroundSync()).resolves.toBe(BackgroundTask.BackgroundTaskResult.Failed);
  await expect(registerBackgroundSync(14)).rejects.toThrow("15 minutes");
  await registerBackgroundSync(15);
  await unregisterBackgroundSync();
  expect(BackgroundTask.registerTaskAsync).toHaveBeenCalledWith(
    BACKGROUND_SYNC_TASK_IDENTIFIER,
    { minimumInterval: 15 },
  );
  expect(BackgroundTask.unregisterTaskAsync).toHaveBeenCalledWith(
    BACKGROUND_SYNC_TASK_IDENTIFIER,
  );
});
