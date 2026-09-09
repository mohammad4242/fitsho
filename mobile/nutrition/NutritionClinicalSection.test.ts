import { expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const nutritionDirectory = dirname(fileURLToPath(import.meta.url));

it("keeps native clinical records inside member-only contracts", async () => {
  const source = await readFile(`${nutritionDirectory}/NutritionClinicalSection.tsx`, "utf8");

  expect(source).toMatch(/getLabDocuments/);
  expect(source).toMatch(/getLabRequests/);
  expect(source).toMatch(/createLabDocumentUploadJob/);
  expect(source).toMatch(/DocumentPicker/);
  expect(source).toMatch(/ExpoPrivateMediaStore/);
  expect(source).toMatch(/grantLabAccess/);
  expect(source).toMatch(/downloadLabDocument/);
  expect(source).toMatch(/Linking/);
  expect(source).toMatch(/getSupplementOrders/);
  expect(source).toMatch(/acknowledgeSupplementOrder/);
  expect(source).toMatch(/<PageHeading/);
  expect(source).toMatch(/<SegmentedControl/);
  expect(source).toMatch(/<DisclosureCard/);
  expect(source).not.toMatch(/FITICIAN · پرونده سلامت/);
  expect(source).not.toMatch(/\/admin\//);
  expect(source).not.toMatch(/\/physician\//);
});

it("blocks supplement acknowledgement when the backend reports a hard safety block", async () => {
  const source = await readFile(`${nutritionDirectory}/NutritionClinicalSection.tsx`, "utf8");

  expect(source).toMatch(/supplementSafetyPresentation/);
  expect(source).toMatch(/safety\.blocked/);
  expect(source).toMatch(/!safety\.blocked/);
});

it("keeps clinical hierarchy as upload and records before filtered supplement detail", async () => {
  const source = await readFile(`${nutritionDirectory}/NutritionClinicalSection.tsx`, "utf8");

  expect(source.indexOf("<PageHeading")).toBeLessThan(source.indexOf("<LabUploadCard"));
  expect(source.indexOf("<LabUploadCard")).toBeLessThan(source.indexOf("<LabRequestsCard"));
  expect(source.indexOf("<LabDocumentsCard")).toBeLessThan(source.indexOf("<SupplementOrdersCard"));
  expect(source).toMatch(/visibleOrders/);
});
