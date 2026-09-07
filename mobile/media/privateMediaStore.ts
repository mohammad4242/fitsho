import { randomUUID } from "expo-crypto";
import { Directory, File, Paths } from "expo-file-system";

import type { BinaryDownload } from "@fitician/core";

import {
  type PrivateMediaStorage,
  type StoredPrivateMediaFile,
  validatePrivateMediaFileName,
  validatePrivateMediaUserId,
} from "./privateMedia";

export const PRIVATE_MEDIA_DIRECTORY = "fitician-private-media";

function userDirectory(userId: string): Directory {
  validatePrivateMediaUserId(userId);
  return new Directory(Paths.cache, PRIVATE_MEDIA_DIRECTORY, encodeURIComponent(userId));
}

export class ExpoPrivateMediaStore implements PrivateMediaStorage {
  async save(
    userId: string,
    fileName: string,
    download: BinaryDownload,
  ): Promise<StoredPrivateMediaFile> {
    const directory = userDirectory(userId);
    const safeFileName = validatePrivateMediaFileName(fileName);
    if (download.bytes.byteLength === 0) {
      throw new Error("Private media response was empty");
    }

    directory.create({ idempotent: true, intermediates: true });
    const destination = new File(directory, safeFileName);
    const temporary = new File(directory, `.${safeFileName}.${randomUUID()}.partial`);
    try {
      temporary.create({ overwrite: true });
      temporary.write(download.bytes);
      await temporary.move(destination, { overwrite: true });
    } catch (error) {
      try {
        if (temporary.exists) {
          temporary.delete();
        }
      } catch {
        // Keep the original storage error.
      }
      throw error;
    }

    return {
      byteSize: download.bytes.byteLength,
      contentType: download.contentType ?? "application/octet-stream",
      fileName: safeFileName,
      uri: destination.uri,
      userId,
    };
  }

  async clearUserFiles(userId: string): Promise<void> {
    const directory = userDirectory(userId);
    if (directory.exists) {
      directory.delete();
    }
  }
}
