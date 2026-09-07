import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

it("cleans local cropped assets on replacement and wizard exit", async () => {
  const source = await readFile(resolve(import.meta.dirname, "BodyAnalysisWizard.tsx"), "utf8");

  expect(source).toMatch(/capturedAssetsRef/);
  expect(source).toMatch(/deleteCapturedAssets\(capturedAssetsRef\.current\)/);
  expect(source).toMatch(/deleteLocalFile\(previous\.uri\)/);
  expect(source).toMatch(/new File\(uri\)/);
  expect(source).not.toMatch(/console\.|Log\./);
});
