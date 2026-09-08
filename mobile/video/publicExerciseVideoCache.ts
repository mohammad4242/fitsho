import { CryptoDigestAlgorithm, digestStringAsync } from "expo-crypto";

import type { BinaryDownload, FiticianTransport } from "@fitician/core";
import {
  mobilePerformanceRecorder,
  type MobilePerformanceRecorder,
} from "../platform/performance";

const VIDEO_EXTENSIONS = new Set([".mp4", ".webm"]);

export const DEFAULT_PUBLIC_VIDEO_CACHE_MAX_BYTES = 128 * 1024 * 1024;
export const DEFAULT_PUBLIC_VIDEO_CACHE_MAX_ENTRIES = 50;

export type PublicVideoCacheFile = {
  readonly cacheKey: string;
  readonly sourcePath: string;
  readonly uri: string;
  readonly byteSize: number;
  readonly contentType: string | null;
};

export interface PublicVideoStore {
  read(cacheKey: string, sourcePath: string): Promise<PublicVideoCacheFile | null>;
  save(
    cacheKey: string,
    sourcePath: string,
    download: BinaryDownload,
  ): Promise<PublicVideoCacheFile>;
  remove(cacheKey: string): Promise<void>;
  clear(): Promise<void>;
}

export interface PublicExerciseVideoCacheOptions {
  readonly performanceRecorder?: MobilePerformanceRecorder;
  readonly transport: Pick<FiticianTransport, "download">;
  readonly storage: PublicVideoStore;
  readonly maxBytes?: number;
  readonly maxEntries?: number;
}

export class PublicVideoCacheError extends Error {
  readonly code = "PUBLIC_VIDEO_CACHE_ERROR";

  constructor(message: string) {
    super(message);
    this.name = "PublicVideoCacheError";
  }
}

export function validatePublicExerciseVideoPath(path: string): string {
  const normalizedPath = path.trim();
  const [pathWithoutQuery] = normalizedPath.split(/[?#]/u);
  const extension = pathWithoutQuery.slice(pathWithoutQuery.lastIndexOf(".")).toLowerCase();
  const pathSegments = pathWithoutQuery.split("/").slice(1);
  if (
    !normalizedPath.startsWith("/media/") ||
    pathWithoutQuery.length <= "/media/".length ||
    pathSegments.some((segment) => segment === "" || segment === "." || segment === "..") ||
    !VIDEO_EXTENSIONS.has(extension) ||
    /[\u0000-\u001f\u007f]/u.test(normalizedPath)
  ) {
    throw new PublicVideoCacheError("Only public /media/ exercise video paths can be cached");
  }
  return normalizedPath;
}

function validateLimit(value: number, name: string): number {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new PublicVideoCacheError(`${name} must be a positive integer`);
  }
  return value;
}

export async function publicExerciseVideoCacheKey(path: string): Promise<string> {
  return digestStringAsync(CryptoDigestAlgorithm.SHA256, validatePublicExerciseVideoPath(path));
}

export class PublicExerciseVideoCache {
  private readonly transport: Pick<FiticianTransport, "download">;
  private readonly storage: PublicVideoStore;
  private readonly maxBytes: number;
  private readonly maxEntries: number;
  private readonly performanceRecorder: MobilePerformanceRecorder;
  private readonly entries = new Map<string, PublicVideoCacheFile>();
  private readonly inFlight = new Map<string, Promise<PublicVideoCacheFile>>();
  private totalBytes = 0;

  constructor(options: PublicExerciseVideoCacheOptions) {
    this.transport = options.transport;
    this.storage = options.storage;
    this.maxBytes = validateLimit(
      options.maxBytes ?? DEFAULT_PUBLIC_VIDEO_CACHE_MAX_BYTES,
      "Public video cache byte limit",
    );
    this.maxEntries = validateLimit(
      options.maxEntries ?? DEFAULT_PUBLIC_VIDEO_CACHE_MAX_ENTRIES,
      "Public video cache entry limit",
    );
    this.performanceRecorder = options.performanceRecorder ?? mobilePerformanceRecorder;
  }

  async getOrDownload(path: string): Promise<PublicVideoCacheFile> {
    const sourcePath = validatePublicExerciseVideoPath(path);
    const cacheKey = await publicExerciseVideoCacheKey(sourcePath);
    const current = this.entries.get(cacheKey);
    if (current !== undefined) {
      this.touch(current);
      return current;
    }

    const pending = this.inFlight.get(cacheKey);
    if (pending !== undefined) {
      return pending;
    }

    const request = this.load(cacheKey, sourcePath);
    this.inFlight.set(cacheKey, request);
    try {
      return await request;
    } finally {
      if (this.inFlight.get(cacheKey) === request) {
        this.inFlight.delete(cacheKey);
      }
    }
  }

  async getCached(path: string): Promise<PublicVideoCacheFile | null> {
    const sourcePath = validatePublicExerciseVideoPath(path);
    const cacheKey = await publicExerciseVideoCacheKey(sourcePath);
    const current = this.entries.get(cacheKey);
    if (current !== undefined) {
      this.touch(current);
      return current;
    }

    const persisted = await this.performanceRecorder.measureAsync(
      "video_cache_hit",
      () => this.storage.read(cacheKey, sourcePath),
    );
    if (
      persisted !== null &&
      persisted.cacheKey === cacheKey &&
      persisted.sourcePath === sourcePath &&
      persisted.byteSize > 0
    ) {
      await this.remember(persisted);
      return persisted;
    }
    if (persisted !== null) {
      await this.storage.remove(cacheKey);
    }
    return null;
  }

  async remove(path: string): Promise<void> {
    const cacheKey = await publicExerciseVideoCacheKey(path);
    const existing = this.entries.get(cacheKey);
    if (existing !== undefined) {
      this.entries.delete(cacheKey);
      this.totalBytes -= existing.byteSize;
    }
    await this.storage.remove(cacheKey);
  }

  async clear(): Promise<void> {
    this.entries.clear();
    this.totalBytes = 0;
    await this.storage.clear();
  }

  private async load(cacheKey: string, sourcePath: string): Promise<PublicVideoCacheFile> {
    const persisted = await this.storage.read(cacheKey, sourcePath);
    if (
      persisted !== null &&
      persisted.cacheKey === cacheKey &&
      persisted.sourcePath === sourcePath &&
      persisted.byteSize > 0
    ) {
      await this.remember(persisted);
      return persisted;
    }
    if (persisted !== null) {
      await this.storage.remove(cacheKey);
    }

    const download = await this.transport.download({
      method: "GET",
      path: sourcePath,
      responseType: "binary",
    });
    this.validateDownload(download);
    if (download.bytes.byteLength > this.maxBytes) {
      throw new PublicVideoCacheError("Exercise video exceeds the public cache byte limit");
    }

    const saved = await this.storage.save(cacheKey, sourcePath, download);
    if (saved.byteSize <= 0 || saved.byteSize > this.maxBytes) {
      await this.storage.remove(cacheKey);
      throw new PublicVideoCacheError("Exercise video exceeds the public cache byte limit");
    }
    await this.remember(saved);
    return saved;
  }

  private validateDownload(download: BinaryDownload): void {
    if (download.bytes.byteLength === 0) {
      throw new PublicVideoCacheError("Public exercise video response was empty");
    }
    if (
      download.contentType !== null &&
      !download.contentType.toLowerCase().startsWith("video/") &&
      download.contentType.toLowerCase() !== "application/octet-stream"
    ) {
      throw new PublicVideoCacheError("Public exercise video response has an invalid content type");
    }
  }

  private touch(entry: PublicVideoCacheFile): void {
    this.entries.delete(entry.cacheKey);
    this.entries.set(entry.cacheKey, entry);
  }

  private async remember(entry: PublicVideoCacheFile): Promise<void> {
    const previous = this.entries.get(entry.cacheKey);
    if (previous !== undefined) {
      this.totalBytes -= previous.byteSize;
    }
    this.entries.set(entry.cacheKey, entry);
    this.totalBytes += entry.byteSize;

    while (this.entries.size > this.maxEntries || this.totalBytes > this.maxBytes) {
      const oldestKey = this.entries.keys().next().value;
      if (typeof oldestKey !== "string") {
        break;
      }
      const oldest = this.entries.get(oldestKey);
      this.entries.delete(oldestKey);
      this.totalBytes -= oldest?.byteSize ?? 0;
      await this.storage.remove(oldestKey);
    }
  }
}
