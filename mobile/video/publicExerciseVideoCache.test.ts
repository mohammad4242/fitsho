import { afterEach, expect, it, vi } from "vitest";

import type { BinaryDownload } from "@fitician/core";

import {
  PublicExerciseVideoCache,
  PublicVideoCacheError,
  type PublicVideoCacheFile,
  type PublicVideoStore,
} from "./publicExerciseVideoCache";
import { MobilePerformanceRecorder } from "../platform/performance";

vi.mock("expo-crypto", () => ({
  CryptoDigestAlgorithm: { SHA256: "SHA-256" },
  digestStringAsync: vi.fn(async (_algorithm: string, value: string) => `hash-${value}`),
}));

afterEach(() => vi.clearAllMocks());

function media(size: number): BinaryDownload {
  return {
    bytes: new Uint8Array(size),
    contentType: "video/mp4",
    filename: "exercise.mp4",
  };
}

function file(key: string, path: string, size: number): PublicVideoCacheFile {
  return {
    byteSize: size,
    cacheKey: key,
    contentType: "video/mp4",
    sourcePath: path,
    uri: `file:///cache/${key}.video`,
  };
}

function store(): PublicVideoStore {
  const files = new Map<string, PublicVideoCacheFile>();
  return {
    clear: vi.fn(async () => files.clear()),
    read: vi.fn(async (key, _path) => files.get(key) ?? null),
    remove: vi.fn(async (key) => {
      files.delete(key);
    }),
    save: vi.fn(async (key, path, download) => {
      const saved = file(key, path, download.bytes.byteLength);
      files.set(key, saved);
      return saved;
    }),
  };
}

it("caches public exercise videos and evicts the least recently used entry", async () => {
  const storage = store();
  const transport = { download: vi.fn(async () => media(2)) };
  const cache = new PublicExerciseVideoCache({
    maxBytes: 5,
    maxEntries: 2,
    storage,
    transport,
  });

  await cache.getOrDownload("/media/exercises/a.mp4");
  await cache.getOrDownload("/media/exercises/b.mp4");
  await cache.getOrDownload("/media/exercises/a.mp4");
  await cache.getOrDownload("/media/exercises/c.mp4");

  expect(transport.download).toHaveBeenCalledTimes(3);
  expect(storage.remove).toHaveBeenCalledWith("hash-/media/exercises/b.mp4");

  await cache.getOrDownload("/media/exercises/b.mp4");
  expect(transport.download).toHaveBeenCalledTimes(4);
});

it("deduplicates concurrent downloads for one public video", async () => {
  const storage = store();
  let resolveDownload!: (value: BinaryDownload) => void;
  const transport = {
    download: vi.fn(
      () => new Promise<BinaryDownload>((resolve) => {
        resolveDownload = resolve;
      }),
    ),
  };
  const cache = new PublicExerciseVideoCache({ storage, transport });

  const first = cache.getOrDownload("/media/exercises/squat.mp4");
  const second = cache.getOrDownload("/media/exercises/squat.mp4");
  await vi.waitFor(() => expect(resolveDownload).toBeTypeOf("function"));
  resolveDownload(media(2));

  await expect(Promise.all([first, second])).resolves.toHaveLength(2);
  expect(transport.download).toHaveBeenCalledOnce();
  expect(storage.save).toHaveBeenCalledOnce();
});

it("finds a persisted video after process restart without downloading it again", async () => {
  const performance = new MobilePerformanceRecorder(() => 0);
  const storage = store();
  const firstTransport = { download: vi.fn(async () => media(2)) };
  const firstCache = new PublicExerciseVideoCache({ storage, transport: firstTransport });
  const path = "/media/exercises/restart.mp4";

  await firstCache.getOrDownload(path);

  const restartedTransport = { download: vi.fn(async () => media(3)) };
  const restartedCache = new PublicExerciseVideoCache({
    performanceRecorder: performance,
    storage,
    transport: restartedTransport,
  });

  await expect(restartedCache.getCached(path)).resolves.toMatchObject({
    sourcePath: path,
    byteSize: 2,
  });
  expect(restartedTransport.download).not.toHaveBeenCalled();
  expect(performance.getSamples()).toEqual([
    {
      budget: 150,
      metric: "video_cache_hit",
      passed: true,
      unit: "ms",
      value: 0,
    },
  ]);
});

it("does not treat API or empty responses as public exercise video cache entries", async () => {
  const storage = store();
  const transport = {
    download: vi.fn().mockResolvedValue(media(2)),
  };
  const cache = new PublicExerciseVideoCache({ storage, transport });

  await expect(cache.getOrDownload("/api/v1/profile/photo/member-1")).rejects.toThrow(
    PublicVideoCacheError,
  );
  transport.download.mockResolvedValue({
    bytes: new Uint8Array(),
    contentType: "video/mp4",
    filename: null,
  });
  await expect(cache.getOrDownload("/media/exercises/empty.mp4")).rejects.toThrow("empty");
  expect(storage.save).not.toHaveBeenCalled();
});

it("clears cached public exercise videos", async () => {
  const storage = store();
  const cache = new PublicExerciseVideoCache({
    storage,
    transport: { download: vi.fn().mockResolvedValue(media(2)) },
  });

  await cache.getOrDownload("/media/exercises/squat.mp4");
  await cache.clear();

  expect(storage.clear).toHaveBeenCalledOnce();
});
