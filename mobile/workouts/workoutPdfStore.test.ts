import { afterEach, expect, it, vi } from "vitest";

import type { BinaryDownload } from "@fitician/core";

const fileSystem = vi.hoisted(() => {
  const directories: FakeDirectory[] = [];
  const files: FakeFile[] = [];
  const persistedFiles = new Set<string>();

  class FakeDirectory {
    readonly uri: string;
    exists = true;
    readonly create = vi.fn();
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
      persistedFiles.add(this.uri);
    });
    readonly write = vi.fn();
    readonly move = vi.fn(async (destination: FakeFile) => {
      destination.exists = true;
      persistedFiles.add(destination.uri);
      persistedFiles.delete(this.uri);
    });
    readonly delete = vi.fn(() => {
      this.exists = false;
      persistedFiles.delete(this.uri);
    });
    readonly info = vi.fn(() => ({ exists: this.exists, size: this.exists ? 4 : 0 }));

    constructor(directory: FakeDirectory, name: string) {
      this.name = name;
      this.uri = `${directory.uri}/${name}`;
      this.exists = persistedFiles.has(this.uri);
      files.push(this);
    }
  }

  return {
    directories,
    files,
    persistedFiles,
    Directory: FakeDirectory,
    File: FakeFile,
    Paths: { document: { uri: "file:///document" } },
  };
});

vi.mock("expo-crypto", () => ({
  randomUUID: vi.fn(() => "temporary-pdf-id"),
}));

vi.mock("expo-file-system", () => ({
  Directory: fileSystem.Directory,
  File: fileSystem.File,
  Paths: fileSystem.Paths,
}));

import { ExpoWorkoutPlanPdfStore } from "./workoutPdfStore";

afterEach(() => {
  fileSystem.directories.length = 0;
  fileSystem.files.length = 0;
  fileSystem.persistedFiles.clear();
  vi.clearAllMocks();
});

const pdf: BinaryDownload = {
  bytes: Uint8Array.from([37, 80, 68, 70]),
  contentType: "application/pdf",
  filename: "server-name.pdf",
};

it("stores workout PDFs atomically in persistent document storage", async () => {
  const store = new ExpoWorkoutPlanPdfStore();

  await expect(store.save("plan-1", pdf)).resolves.toMatchObject({
    byteSize: 4,
    fileName: "fitician-workout-plan-plan-1.pdf",
    planId: "plan-1",
  });

  const directory = fileSystem.directories[0];
  const temporary = fileSystem.files.find((file) => file.name.includes("temporary-pdf-id"));
  const destination = fileSystem.files.find((file) => file.name === "fitician-workout-plan-plan-1.pdf");
  expect(directory.create).toHaveBeenCalledWith({ idempotent: true, intermediates: true });
  expect(temporary?.write).toHaveBeenCalledWith(pdf.bytes);
  expect(temporary?.move).toHaveBeenCalledWith(destination, { overwrite: true });
});

it("returns a persisted PDF after a new store instance is created", async () => {
  const first = new ExpoWorkoutPlanPdfStore();
  await first.save("plan-1", pdf);

  const second = new ExpoWorkoutPlanPdfStore();

  await expect(second.get("plan-1")).resolves.toMatchObject({
    fileName: "fitician-workout-plan-plan-1.pdf",
    planId: "plan-1",
  });
});

it("rejects empty or non-PDF responses and clears persistent plan files", async () => {
  const store = new ExpoWorkoutPlanPdfStore();

  await expect(store.save("plan-1", { ...pdf, bytes: new Uint8Array() })).rejects.toThrow("empty");
  await expect(store.save("plan-1", { ...pdf, contentType: "image/jpeg" })).rejects.toThrow("PDF");
  await store.clear();
  expect(fileSystem.directories.at(-1)?.delete).toHaveBeenCalledOnce();
});
