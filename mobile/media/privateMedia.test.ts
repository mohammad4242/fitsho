import { afterEach, expect, it, vi } from "vitest";

import type { BinaryDownload } from "@fitician/core";

import {
  PrivateMediaClient,
  type PrivateMediaStorage,
  type StoredPrivateMediaFile,
} from "./privateMedia";

afterEach(() => vi.clearAllMocks());

function download(): BinaryDownload {
  return {
    bytes: Uint8Array.from([1, 2, 3]),
    contentType: "image/jpeg",
    filename: "server-name.jpg",
  };
}

function storedFile(): StoredPrivateMediaFile {
  return {
    byteSize: 3,
    contentType: "image/jpeg",
    fileName: "profile.jpg",
    uri: "file:///cache/fitician-private-media/member-1/profile.jpg",
    userId: "member-1",
  };
}

it("downloads private media through the authenticated binary transport", async () => {
  const authClient = {
    download: vi.fn().mockResolvedValue(download()),
  };
  const storage: PrivateMediaStorage = {
    clearUserFiles: vi.fn().mockResolvedValue(undefined),
    save: vi.fn().mockResolvedValue(storedFile()),
  };
  const client = new PrivateMediaClient({
    authClient,
    storage,
    userId: "member-1",
  });

  await expect(
    client.download({
      fileName: "profile.jpg",
      path: "/api/v1/profile/photo/member-1",
      query: { version: "2" },
    }),
  ).resolves.toEqual(storedFile());

  expect(authClient.download).toHaveBeenCalledWith({
    headers: {
      "Cache-Control": "no-store",
      Pragma: "no-cache",
    },
    method: "GET",
    path: "/api/v1/profile/photo/member-1",
    query: { version: "2" },
    responseType: "binary",
  });
  expect(storage.save).toHaveBeenCalledWith("member-1", "profile.jpg", download());
});

it("cleans all private files for the authenticated user", async () => {
  const storage: PrivateMediaStorage = {
    clearUserFiles: vi.fn().mockResolvedValue(undefined),
    save: vi.fn(),
  };
  const client = new PrivateMediaClient({
    authClient: { download: vi.fn() },
    storage,
    userId: "member-1",
  });

  await client.clearUserFiles();

  expect(storage.clearUserFiles).toHaveBeenCalledWith("member-1");
});

it("rejects unsafe local names and empty private responses", async () => {
  const authClient = {
    download: vi.fn().mockResolvedValue(download()),
  };
  const storage: PrivateMediaStorage = {
    clearUserFiles: vi.fn(),
    save: vi.fn(),
  };
  const client = new PrivateMediaClient({
    authClient,
    storage,
    userId: "member-1",
  });

  await expect(
    client.download({ fileName: "../secret.jpg", path: "/api/v1/private/file" }),
  ).rejects.toThrow("safe");

  authClient.download.mockResolvedValue({
    bytes: new Uint8Array(),
    contentType: "image/jpeg",
    filename: null,
  });
  await expect(
    client.download({ fileName: "empty.jpg", path: "/api/v1/private/file" }),
  ).rejects.toThrow("empty");
  expect(storage.save).not.toHaveBeenCalled();
});
