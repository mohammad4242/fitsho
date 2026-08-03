import type { BodyPhotoView } from "./types";

export type ProcessedBodyPhoto = {
  file: File;
  previewUrl: string;
  originalHeight: number;
  cropTop: number;
  cropBottom: number;
  cropConfidence: number;
  processedSha256: string;
  cropEvidenceSha256: string;
};

export interface BodyPhotoProcessor {
  process(file: File, view: BodyPhotoView): Promise<ProcessedBodyPhoto>;
}

const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const minimumCropRatio = 0.15;
const targetWidth = 1200;

export class BrowserBodyPhotoProcessor implements BodyPhotoProcessor {
  async process(file: File, _view: BodyPhotoView): Promise<ProcessedBodyPhoto> {
    if (!allowedTypes.has(file.type)) {
      throw new Error("unsupported_format");
    }
    if (file.size === 0 || file.size > 8 * 1024 * 1024) {
      throw new Error("invalid_file_size");
    }

    const image = await loadImage(file);
    if (image.naturalWidth < 256 || image.naturalHeight < 512) {
      throw new Error("invalid_resolution");
    }
    const cropTop = Math.ceil(image.naturalHeight * minimumCropRatio);
    const cropBottom = image.naturalHeight;
    const cropHeight = cropBottom - cropTop;
    const outputWidth = Math.min(targetWidth, image.naturalWidth);
    const outputHeight = Math.round((cropHeight / image.naturalWidth) * outputWidth);
    const canvas = document.createElement("canvas");
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    const context = canvas.getContext("2d");
    if (context === null) {
      throw new Error("canvas_unavailable");
    }
    // Drawing to a new canvas normalizes EXIF orientation and removes metadata.
    context.drawImage(
      image,
      0,
      cropTop,
      image.naturalWidth,
      cropHeight,
      0,
      0,
      outputWidth,
      outputHeight,
    );
    const blob = await canvasToBlob(canvas);
    const processedBytes = await blob.arrayBuffer();
    const processedSha256 = await sha256(processedBytes);
    const cropEvidenceSha256 = await sha256(
      new TextEncoder().encode(
        `v1:${processedSha256}:${image.naturalHeight}:${cropTop}:${cropBottom}`,
      ).buffer,
    );
    const processedFile = new File([blob], `body-photo-${Date.now()}.jpg`, {
      type: "image/jpeg",
    });
    return {
      file: processedFile,
      previewUrl: URL.createObjectURL(processedFile),
      originalHeight: image.naturalHeight,
      cropTop,
      cropBottom,
      cropConfidence: 0.8,
      processedSha256,
      cropEvidenceSha256,
    };
  }
}

export const browserBodyPhotoProcessor = new BrowserBodyPhotoProcessor();

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("invalid_image"));
    };
    image.src = url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob === null) {
        reject(new Error("processing_failed"));
        return;
      }
      resolve(blob);
    }, "image/jpeg", 0.9);
  });
}

async function sha256(value: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", value);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
