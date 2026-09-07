import { afterEach, expect, it, vi } from "vitest";

import type { BinaryDownload } from "@fitician/core";

const fileSystem = vi.hoisted(() => {
  const directories: FakeDirectory[] = [];
  const files: FakeFile[] = [];

  class FakeDirectory {
    readonly uri: string;
    exists = true;
    readonly create = vi.fn(() => {
      this.exists = true;
    });
    readonly delete = vi.fn(() => {
      this.exists = false;
    });

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
    readonly delete = vi.fn(() => {
      this.exists = false;
    });
    readonly move = vi.fn(async () => undefined);

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
  randomUUID: vi.fn(() => "temporary-file-id"),
}));

vi.mock("expo-file-system", () => ({
  Directory: fileSystem.Directory,
  File: fileSystem.File,
  Paths: fileSystem.Paths,
}));

import { ExpoPrivateMediaStore } from "./privateMediaStore";

afterEach(() => {
  fileSystem.directories.length = 0;
  fileSystem.files.length = 0;
  vi.clearAllMocks();
});

const media: BinaryDownload = {
  bytes: Uint8Array.from([1, 2, 3]),
  contentType: "image/jpeg",
  filename: "server.jpg",
};

it("writes private media atomically inside a user-scoped cache directory", async () => {
  const store = new ExpoPrivateMediaStore();

  await expect(store.save("member-1", "profile.jpg", media)).resolves.toMatchObject({
    byteSize: 3,
    contentType: "image/jpeg",
    fileName: "profile.jpg",
    userId: "member-1",
  });

  const directory = fileSystem.directories[0];
  const destination = fileSystem.files.find((file) => file.name === "profile.jpg");
  const temporary = fileSystem.files.find((file) => file.name.includes("temporary-file-id"));
  expect(directory.create).toHaveBeenCalledWith({ idempotent: true, intermediates: true });
  expect(temporary?.write).toHaveBeenCalledWith(media.bytes);
  expect(temporary?.move).toHaveBeenCalledWith(destination, { overwrite: true });
});

it("deletes the complete user-scoped private media directory", async () => {
  const store = new ExpoPrivateMediaStore();

  await store.clearUserFiles("member-1");

  expect(fileSystem.directories.at(-1)?.delete).toHaveBeenCalledOnce();
});
