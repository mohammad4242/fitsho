import { afterEach, expect, it, vi } from "vitest";

import type { BinaryDownload } from "@fitician/core";

const fileSystem = vi.hoisted(() => {
  const directories: FakeDirectory[] = [];
  const files: FakeFile[] = [];

  class FakeDirectory {
    readonly uri: string;
    exists = true;
    readonly create = vi.fn();
    readonly delete = vi.fn();

    constructor(...parts: unknown[]) {
      this.uri = parts
        .map((part) => (typeof part === "string" ? part : (part as { uri: string }).uri))
        .join("/");
      directories.push(this);
    }
  }

  class FakeFile {
    readonly uri: string;
    readonly name: string;
    exists = false;
    readonly create = vi.fn(() => {
      this.exists = true;
    });
    readonly write = vi.fn();
    readonly move = vi.fn(async () => undefined);
    readonly delete = vi.fn(() => {
      this.exists = false;
    });
    readonly info = vi.fn(() => ({ exists: this.exists, size: 3 }));

    constructor(directory: FakeDirectory, name: string) {
      this.name = name;
      this.uri = `${directory.uri}/${name}`;
      files.push(this);
    }
  }

  return {
    directories,
    files,
    Directory: FakeDirectory,
    File: FakeFile,
    Paths: { cache: { uri: "file:///cache" } },
  };
});

vi.mock("expo-crypto", () => ({
  randomUUID: vi.fn(() => "temporary-video-id"),
}));

vi.mock("expo-file-system", () => ({
  Directory: fileSystem.Directory,
  File: fileSystem.File,
  Paths: fileSystem.Paths,
}));

import { ExpoPublicExerciseVideoStore } from "./publicExerciseVideoStore";

afterEach(() => {
  fileSystem.directories.length = 0;
  fileSystem.files.length = 0;
  vi.clearAllMocks();
});

const media: BinaryDownload = {
  bytes: Uint8Array.from([1, 2, 3]),
  contentType: "video/mp4",
  filename: "exercise.mp4",
};

it("stores public videos in an app cache directory with hashed filenames", async () => {
  const store = new ExpoPublicExerciseVideoStore();

  await expect(
    store.save("a".repeat(64), "/media/exercises/squat.mp4", media),
  ).resolves.toMatchObject({
    byteSize: 3,
    cacheKey: "a".repeat(64),
    sourcePath: "/media/exercises/squat.mp4",
  });

  const temporary = fileSystem.files.find((file) => file.name.includes("temporary-video-id"));
  const destination = fileSystem.files.find((file) => file.name === `${"a".repeat(64)}.video`);
  expect(temporary?.write).toHaveBeenCalledWith(media.bytes);
  expect(temporary?.move).toHaveBeenCalledWith(destination, { overwrite: true });
});

it("clears the public video cache directory", async () => {
  const store = new ExpoPublicExerciseVideoStore();

  await store.clear();

  expect(fileSystem.directories.at(-1)?.delete).toHaveBeenCalledOnce();
});
