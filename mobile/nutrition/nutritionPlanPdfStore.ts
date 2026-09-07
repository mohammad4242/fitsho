import { randomUUID } from "expo-crypto";
import { Directory, File, Paths } from "expo-file-system";

import type { BinaryDownload } from "@fitician/core";

import { nutritionPlanPdfFilename } from "./nutritionPlanModel";

export const NUTRITION_PLAN_PDF_DIRECTORY = "fitician-nutrition-plans";

export type StoredNutritionPlanPdf = {
  readonly byteSize: number;
  readonly fileName: string;
  readonly planId: string;
  readonly uri: string;
};

function planDirectory(): Directory {
  return new Directory(Paths.document, NUTRITION_PLAN_PDF_DIRECTORY);
}

function planFile(planId: string): { directory: Directory; file: File; fileName: string } {
  const directory = planDirectory();
  const fileName = nutritionPlanPdfFilename(planId);
  return { directory, file: new File(directory, fileName), fileName };
}

function validatePdf(planId: string, download: BinaryDownload): void {
  if (planId.trim().length === 0) {
    throw new TypeError("A nutrition plan id is required");
  }
  if (download.bytes.byteLength === 0) {
    throw new TypeError("Nutrition plan PDF cannot be empty");
  }
  const contentType = download.contentType?.split(";", 1)[0]?.trim().toLowerCase();
  if (contentType !== undefined && contentType !== null && contentType !== "application/pdf") {
    throw new TypeError("Nutrition plan download is not a PDF");
  }
  if (
    download.bytes[0] !== 37
    || download.bytes[1] !== 80
    || download.bytes[2] !== 68
    || download.bytes[3] !== 70
  ) {
    throw new TypeError("Nutrition plan download is not a PDF");
  }
}

export class ExpoNutritionPlanPdfStore {
  async get(planId: string): Promise<StoredNutritionPlanPdf | null> {
    const { file, fileName } = planFile(planId);
    if (!file.exists) return null;
    const info = file.info();
    if (!info.exists || info.size === undefined || info.size <= 0) return null;
    return { byteSize: info.size, fileName, planId, uri: file.uri };
  }

  async save(planId: string, download: BinaryDownload): Promise<StoredNutritionPlanPdf> {
    validatePdf(planId, download);
    const { directory, file, fileName } = planFile(planId);
    directory.create({ idempotent: true, intermediates: true });
    const temporary = new File(directory, `.${fileName}.${randomUUID()}.partial`);
    try {
      temporary.create({ overwrite: true });
      temporary.write(download.bytes);
      await temporary.move(file, { overwrite: true });
    } catch (error) {
      try {
        if (temporary.exists) temporary.delete();
      } catch {
        // Keep the original storage error.
      }
      throw error;
    }
    return { byteSize: download.bytes.byteLength, fileName, planId, uri: file.uri };
  }

  async remove(planId: string): Promise<void> {
    const { file } = planFile(planId);
    if (file.exists) file.delete();
  }

  async clear(): Promise<void> {
    const directory = planDirectory();
    if (directory.exists) directory.delete();
  }
}
