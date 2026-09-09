import { expect, it, vi } from "vitest";

import type { BodyPhoto } from "@fitician/core/body-photos";

vi.mock("../media/privateMedia", () => ({ PrivateMediaClient: class PrivateMediaClient {} }));
vi.mock("../media/privateMediaStore", () => ({ ExpoPrivateMediaStore: class ExpoPrivateMediaStore {} }));

import { loadPrivateBodyPhotoUris } from "./bodyPhotoPrivateMedia";

it("downloads body photos through the authenticated private-media client", async () => {
  const client = {
    download: vi.fn()
      .mockResolvedValueOnce({ uri: "file:///private/front.jpg" })
      .mockResolvedValueOnce({ uri: "file:///private/side.jpg" }),
  };
  const photos = [
    { view: "front", content_url: "/private/front" },
    { view: "side", content_url: "/private/side" },
  ] as unknown as BodyPhoto[];

  await expect(loadPrivateBodyPhotoUris(photos, client as never, "body-analysis-session-1"))
    .resolves.toEqual({
      front: "file:///private/front.jpg",
      side: "file:///private/side.jpg",
    });

  expect(client.download).toHaveBeenNthCalledWith(1, {
    fileName: "body-analysis-session-1-front.jpg",
    path: "/private/front",
  });
  expect(client.download).toHaveBeenNthCalledWith(2, {
    fileName: "body-analysis-session-1-side.jpg",
    path: "/private/side",
  });
});

it("drops an unavailable private photo without exposing its protected URL", async () => {
  const client = {
    download: vi.fn().mockRejectedValue(new Error("download failed")),
  };
  const photo = { view: "back", content_url: "/private/back" } as unknown as BodyPhoto;

  await expect(loadPrivateBodyPhotoUris([photo], client as never, "body-analysis-session-1"))
    .resolves.toEqual({});
});
