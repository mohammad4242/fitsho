import type { BodyPhoto, BodyPhotoView } from "@fitician/core/body-photos";

import type { AuthenticatedBodyPhotoDownload } from "./bodyPhotoApi";
import { PrivateMediaClient } from "../media/privateMedia";
import { ExpoPrivateMediaStore } from "../media/privateMediaStore";

export type PrivateBodyPhotoUris = Partial<Record<BodyPhotoView, string>>;

export function createPrivateBodyPhotoClient(
  download: AuthenticatedBodyPhotoDownload,
  userId: string | null | undefined,
): PrivateMediaClient | null {
  if (userId === null || userId === undefined) return null;
  return new PrivateMediaClient({
    authClient: { download },
    storage: new ExpoPrivateMediaStore(),
    userId,
  });
}

export async function loadPrivateBodyPhotoUris(
  photos: readonly BodyPhoto[],
  client: PrivateMediaClient,
  fileNamePrefix: string,
): Promise<PrivateBodyPhotoUris> {
  const safePrefix = fileNamePrefix.replace(/[^A-Za-z0-9._-]/gu, "_");
  const entries = await Promise.all(photos.map(async (photo) => {
    try {
      const stored = await client.download({
        fileName: `${safePrefix}-${photo.view}.jpg`,
        path: photo.content_url,
      });
      return [photo.view, stored.uri] as const;
    } catch {
      return null;
    }
  }));
  return Object.fromEntries(
    entries.filter((entry): entry is readonly [BodyPhotoView, string] => entry !== null),
  );
}
