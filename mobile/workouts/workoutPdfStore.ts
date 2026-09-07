import { randomUUID } from "expo-crypto";
import { Directory, File, Paths } from "expo-file-system";

import type { BinaryDownload } from "@fitician/core";

import { workoutPlanPdfFilename } from "./workoutModel";

export const WORKOUT_PLAN_PDF_DIRECTORY = "fitician-workout-plans";

export type StoredWorkoutPlanPdf = {
  readonly byteSize: number;
  readonly fileName: string;
  readonly planId: string;
  readonly uri: string;
};

function planDirectory(): Directory {
  return new Directory(Paths.document, WORKOUT_PLAN_PDF_DIRECTORY);
}

function planFile(planId: string): { directory: Directory; file: File; fileName: string } {
  const directory = planDirectory();
  const fileName = workoutPlanPdfFilename(planId);
  return { directory, file: new File(directory, fileName), fileName };
}

function validatePdf(planId: string, download: BinaryDownload): void {
  if (planId.trim().length === 0) {
    throw new TypeError("A workout plan id is required");
  }
  if (download.bytes.byteLength === 0) {
    throw new TypeError("Workout plan PDF cannot be empty");
  }
  const contentType = download.contentType?.split(";", 1)[0]?.trim().toLowerCase();
  if (contentType !== undefined && contentType !== null && contentType !== "application/pdf") {
    throw new TypeError("Workout plan download is not a PDF");
  }
  if (
    download.bytes[0] !== 37
    || download.bytes[1] !== 80
    || download.bytes[2] !== 68
    || download.bytes[3] !== 70
  ) {
    throw new TypeError("Workout plan download is not a PDF");
  }
}

export class ExpoWorkoutPlanPdfStore {
  async get(planId: string): Promise<StoredWorkoutPlanPdf | null> {
    const { file, fileName } = planFile(planId);
    if (!file.exists) return null;
    const info = file.info();
    if (!info.exists || info.size === undefined || info.size <= 0) return null;
    return { byteSize: info.size, fileName, planId, uri: file.uri };
  }

  async save(planId: string, download: BinaryDownload): Promise<StoredWorkoutPlanPdf> {
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
