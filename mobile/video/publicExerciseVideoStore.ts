import { randomUUID } from "expo-crypto";
import { Directory, File, Paths } from "expo-file-system";

import type { BinaryDownload } from "@fitician/core";

import {
  type PublicVideoCacheFile,
  type PublicVideoStore,
} from "./publicExerciseVideoCache";

export const PUBLIC_EXERCISE_VIDEO_DIRECTORY = "fitician-public-exercise-videos";

function validateCacheKey(cacheKey: string): string {
  if (!/^[a-f0-9]{64}$/u.test(cacheKey)) {
    throw new TypeError("Public video cache keys must be SHA-256 hex strings");
  }
  return cacheKey;
}

function cacheDirectory(): Directory {
  return new Directory(Paths.cache, PUBLIC_EXERCISE_VIDEO_DIRECTORY);
}

function cacheFile(directory: Directory, cacheKey: string): File {
  return new File(directory, `${validateCacheKey(cacheKey)}.video`);
}

export class ExpoPublicExerciseVideoStore implements PublicVideoStore {
  async read(cacheKey: string, sourcePath: string): Promise<PublicVideoCacheFile | null> {
    const file = cacheFile(cacheDirectory(), cacheKey);
    if (!file.exists) {
      return null;
    }
    const info = file.info();
    if (!info.exists || !info.size || info.size <= 0) {
      return null;
    }
    return {
      byteSize: info.size,
      cacheKey,
      contentType: "video/*",
      sourcePath,
      uri: file.uri,
    };
  }

  async save(
    cacheKey: string,
    sourcePath: string,
    download: BinaryDownload,
  ): Promise<PublicVideoCacheFile> {
    const directory = cacheDirectory();
    const safeCacheKey = validateCacheKey(cacheKey);
    if (download.bytes.byteLength === 0) {
      throw new TypeError("Public exercise video cannot be empty");
    }
    directory.create({ idempotent: true, intermediates: true });
    const destination = cacheFile(directory, safeCacheKey);
    const temporary = new File(directory, `.${safeCacheKey}.${randomUUID()}.partial`);
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
      cacheKey: safeCacheKey,
      contentType: download.contentType,
      sourcePath,
      uri: destination.uri,
    };
  }

  async remove(cacheKey: string): Promise<void> {
    const file = cacheFile(cacheDirectory(), cacheKey);
    if (file.exists) {
      file.delete();
    }
  }

  async clear(): Promise<void> {
    const directory = cacheDirectory();
    if (directory.exists) {
      directory.delete();
    }
  }
}
