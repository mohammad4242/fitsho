import { describe, expect, it, vi } from "vitest";

import {
  normalizeImageForUpload,
} from "./imageNormalization";

const HEIC_SIGNATURE = new Uint8Array([
  0, 0, 0, 24,
  0x66, 0x74, 0x79, 0x70,
  0x68, 0x65, 0x69, 0x63,
  0, 0, 0, 0,
  0x6d, 0x69, 0x66, 0x31,
]);

function heicFile(options: { name?: string; type?: string; bytes?: Uint8Array } = {}) {
  const bytes = options.bytes ?? HEIC_SIGNATURE;
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;

  return new File([buffer], options.name ?? "camera.heic", {
    type: options.type ?? "image/heic",
    lastModified: 123,
  });
}

describe("normalizeImageForUpload", () => {
  it("converts a signature-validated HEIC image to a JPEG File", async () => {
    const convertHeif = vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));

    const normalized = await normalizeImageForUpload(heicFile(), { convertHeif });

    expect(convertHeif).toHaveBeenCalledOnce();
    expect(normalized).toMatchObject({
      name: "camera.jpg",
      type: "image/jpeg",
      lastModified: 123,
    });
  });

  it("accepts an iPhone HEIF file when Safari reports only its extension", async () => {
    const convertHeif = vi.fn().mockResolvedValue(new Blob(["jpeg"], { type: "image/jpeg" }));

    const normalized = await normalizeImageForUpload(heicFile({ name: "camera.HEIF", type: "" }), {
      convertHeif,
    });

    expect(convertHeif).toHaveBeenCalledOnce();
    expect(normalized.type).toBe("image/jpeg");
  });

  it("keeps an already-supported image unchanged", async () => {
    const image = new File([new Uint8Array([0xff, 0xd8, 0xff]).buffer], "photo.jpg", {
      type: "image/jpeg",
    });
    const convertHeif = vi.fn();

    await expect(normalizeImageForUpload(image, { convertHeif })).resolves.toBe(image);
    expect(convertHeif).not.toHaveBeenCalled();
  });

  it("rejects a declared HEIC file whose binary signature is not HEIF", async () => {
    await expect(normalizeImageForUpload(heicFile({ bytes: new Uint8Array([1, 2, 3, 4]) }))).rejects
      .toMatchObject({ code: "invalid_heif" });
  });
});
