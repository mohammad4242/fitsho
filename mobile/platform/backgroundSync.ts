import * as BackgroundTask from "expo-background-task";
import * as TaskManager from "expo-task-manager";

export const BACKGROUND_SYNC_TASK_IDENTIFIER = "fitician-background-sync";
export const MIN_BACKGROUND_SYNC_INTERVAL_MINUTES = 15;

export type BackgroundSyncHandler = () => Promise<void>;

let backgroundSyncHandler: BackgroundSyncHandler | null = null;

export function setBackgroundSyncHandler(handler: BackgroundSyncHandler | null): void {
  backgroundSyncHandler = handler;
}

export async function executeBackgroundSync(): Promise<BackgroundTask.BackgroundTaskResult> {
  if (backgroundSyncHandler === null) {
    return BackgroundTask.BackgroundTaskResult.Success;
  }
  try {
    await backgroundSyncHandler();
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
}

TaskManager.defineTask(BACKGROUND_SYNC_TASK_IDENTIFIER, executeBackgroundSync);

export async function registerBackgroundSync(
  minimumIntervalMinutes: number = MIN_BACKGROUND_SYNC_INTERVAL_MINUTES,
): Promise<void> {
  if (
    !Number.isInteger(minimumIntervalMinutes) ||
    minimumIntervalMinutes < MIN_BACKGROUND_SYNC_INTERVAL_MINUTES
  ) {
    throw new RangeError("Background synchronization requires an interval of at least 15 minutes");
  }
  await BackgroundTask.registerTaskAsync(BACKGROUND_SYNC_TASK_IDENTIFIER, {
    minimumInterval: minimumIntervalMinutes,
  });
}

export async function unregisterBackgroundSync(): Promise<void> {
  await BackgroundTask.unregisterTaskAsync(BACKGROUND_SYNC_TASK_IDENTIFIER);
}
