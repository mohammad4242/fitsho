import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(mobileRoot, "..");
const androidAssetRoot = resolve(
  mobileRoot,
  "modules/fitician-body-vision/android/src/main/assets/body_vision",
);

const models = [
  "pose_landmarker_lite.task",
  "selfie_segmenter.tflite",
] as const;

async function sha256(path: string): Promise<string> {
  const contents = await readFile(path);
  return createHash("sha256").update(contents).digest("hex");
}

describe("native body vision model packaging", () => {
  it("packages the exact approved web model bytes in Android assets", async () => {
    for (const model of models) {
      const webPath = resolve(projectRoot, "frontend/public/mediapipe/models", model);
      const androidPath = resolve(androidAssetRoot, model);
      const [webStat, androidStat] = await Promise.all([stat(webPath), stat(androidPath)]);

      expect(webStat.isFile()).toBe(true);
      expect(androidStat.isFile()).toBe(true);
      expect(androidStat.size).toBe(webStat.size);
      await expect(sha256(androidPath)).resolves.toBe(await sha256(webPath));
    }
  });

  it("uses the same asset paths as the native MediaPipe implementation", async () => {
    const nativeSource = await readFile(
      resolve(
        mobileRoot,
        "modules/fitician-body-vision/android/src/main/java/com/margelo/nitro/fitician/bodyvision/FiticianBodyVision.kt",
      ),
      "utf8",
    );

    for (const model of models) {
      expect(nativeSource).toContain(`body_vision/${model}`);
    }
  });
});
