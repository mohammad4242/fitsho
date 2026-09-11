import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("uses the shared platform-aware notification bootstrap at the root", async () => {
  const source = await readFile(
    resolve(import.meta.dirname, "../app/_layout.tsx"),
    "utf8",
  );

  expect(source).toContain("prepareNotifications");
  expect(source).toContain("getNativePushToken");
  expect(source).toContain("registerNotifications");
  expect(source).not.toContain("prepareAndroidNotifications");
  expect(source).not.toContain("getAndroidFcmToken");
  expect(source).not.toContain("registerAndroidNotifications");
});
