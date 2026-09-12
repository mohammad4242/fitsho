import { readFileSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const fixtureBase64 = readFileSync(resolve(here, "fixtures/iphone-image4.heic")).toString("base64");

function imageNormalizationChunk(): string {
  const assets = readdirSync(resolve(here, "../dist/assets"));
  const chunk = assets.find((file) => /^imageNormalization-[^/]+\.js$/.test(file));
  if (chunk === undefined) throw new Error("imageNormalization production chunk is missing");
  return chunk;
}

test("converts a real HEIC fixture to a valid JPEG in the production browser bundle", async ({ page, browserName }) => {
  const decoderRequests: string[] = [];
  page.on("request", (request) => {
    if (/heic_dec-[^/]+\.wasm$/.test(request.url())) decoderRequests.push(request.url());
  });
  await page.goto("/", { waitUntil: "networkidle" });
  const result = await page.evaluate(async ({ base64, chunk }) => {
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    const source = new File([bytes], "iphone-image4.heic", { type: "image/heic" });
    const module = await import(`/assets/${chunk}`);
    const candidates = Object.values(module).filter((value): value is (file: File) => Promise<File> => (
      typeof value === "function"
    ));
    let normalize: ((file: File) => Promise<File>) | undefined;
    for (const candidate of candidates) {
      try {
        const probe = await candidate(new File([new Uint8Array([0xff, 0xd8, 0xff])], "probe.jpg", {
          type: "image/jpeg",
        }));
        if (probe instanceof File && probe.type === "image/jpeg") {
          normalize = candidate;
          break;
        }
      } catch {
        // The chunk also exports its error class; only the normalizer accepts a JPEG file.
      }
    }
    if (normalize === undefined) throw new Error("normalizer export is missing");
    const normalized = await normalize(source);
    const signature = new Uint8Array(await normalized.slice(0, 3).arrayBuffer());
    return {
      name: normalized.name,
      size: normalized.size,
      type: normalized.type,
      signature: [...signature],
    };
  }, { base64: fixtureBase64, chunk: imageNormalizationChunk() });

  if (browserName === "chromium") expect(decoderRequests).toHaveLength(1);
  expect(result).toMatchObject({
    name: "iphone-image4.jpg",
    type: "image/jpeg",
    signature: [0xff, 0xd8, 0xff],
  });
  expect(result.size).toBeGreaterThan(0);
});
