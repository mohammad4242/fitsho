const SUPPORTED_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

const HEIF_TYPES = new Set([
  "image/heic",
  "image/heif",
]);

const HEIF_BRANDS = new Set([
  "heic",
  "heix",
  "hevc",
  "hevx",
  "heim",
  "heis",
  "mif1",
  "msf1",
]);

export type UserImageNormalizationErrorCode =
  | "unsupported_image_format"
  | "invalid_heif"
  | "heif_decode_failed"
  | "invalid_normalized_image"
  | "image_too_large";

export class UserImageNormalizationError extends Error {
  readonly code: UserImageNormalizationErrorCode;

  constructor(code: UserImageNormalizationErrorCode) {
    super(code);
    this.name = "UserImageNormalizationError";
    this.code = code;
  }
}

export type HeifConverter = (file: File) => Promise<Blob>;

export type NormalizeImageForUploadOptions = {
  convertHeif?: HeifConverter;
  maximumInputBytes?: number;
  maximumOutputBytes?: number;
  maximumPixelCount?: number;
};

const defaultMaximumInputBytes = 8 * 1024 * 1024;
const defaultMaximumOutputBytes = 8 * 1024 * 1024;
const defaultMaximumPixelCount = 20_000_000;

export async function normalizeImageForUpload(
  file: File,
  options: NormalizeImageForUploadOptions = {},
): Promise<File> {
  if (SUPPORTED_IMAGE_TYPES.has(file.type)) return file;
  if (!isHeifSource(file)) throw new UserImageNormalizationError("unsupported_image_format");

  const maximumInputBytes = options.maximumInputBytes ?? defaultMaximumInputBytes;
  if (file.size === 0 || file.size > maximumInputBytes) {
    throw new UserImageNormalizationError("image_too_large");
  }

  const header = new Uint8Array(await file.slice(0, 32).arrayBuffer());
  if (!hasHeifSignature(header)) throw new UserImageNormalizationError("invalid_heif");

  const convertHeif = options.convertHeif
    ?? ((input) => convertHeifWithBrowser(input, options.maximumPixelCount ?? defaultMaximumPixelCount));
  let jpeg: Blob;
  try {
    jpeg = await convertHeif(file);
  } catch {
    throw new UserImageNormalizationError("heif_decode_failed");
  }

  const maximumOutputBytes = options.maximumOutputBytes ?? defaultMaximumOutputBytes;
  if (jpeg.type !== "image/jpeg" || jpeg.size === 0) {
    throw new UserImageNormalizationError("invalid_normalized_image");
  }
  if (jpeg.size > maximumOutputBytes) throw new UserImageNormalizationError("image_too_large");

  return new File([jpeg], jpegFileName(file.name), {
    type: "image/jpeg",
    lastModified: file.lastModified,
  });
}

function isHeifSource(file: File): boolean {
  if (HEIF_TYPES.has(file.type.toLowerCase())) return true;
  return /\.hei[cf]$/i.test(file.name);
}

function hasHeifSignature(bytes: Uint8Array): boolean {
  if (bytes.length < 12 || bytes[4] !== 0x66 || bytes[5] !== 0x74 || bytes[6] !== 0x79 || bytes[7] !== 0x70) {
    return false;
  }
  const ascii = new TextDecoder("ascii").decode(bytes);
  for (let offset = 8; offset + 4 <= ascii.length; offset += 4) {
    if (HEIF_BRANDS.has(ascii.slice(offset, offset + 4).toLowerCase())) return true;
  }
  return false;
}

async function convertHeifWithBrowser(file: File, maximumPixelCount: number): Promise<Blob> {
  try {
    return await convertHeifWithNativeBrowser(file, maximumPixelCount);
  } catch {
    return convertHeifWithWasm(file, maximumPixelCount);
  }
}

async function convertHeifWithNativeBrowser(file: File, maximumPixelCount: number): Promise<Blob> {
  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await loadImage(sourceUrl);
    const sourceWidth = image.naturalWidth || image.width;
    const sourceHeight = image.naturalHeight || image.height;
    if (!sourceWidth || !sourceHeight) throw new UserImageNormalizationError("heif_decode_failed");

    const scale = Math.min(1, Math.sqrt(maximumPixelCount / (sourceWidth * sourceHeight)));
    const width = Math.max(1, Math.round(sourceWidth * scale));
    const height = Math.max(1, Math.round(sourceHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (context === null) throw new UserImageNormalizationError("heif_decode_failed");
    context.drawImage(image, 0, 0, width, height);
    return canvasToJpeg(canvas);
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

async function convertHeifWithWasm(file: File, maximumPixelCount: number): Promise<Blob> {
  const { decode } = await import("@discourse/heic");
  const decoded = await decode(await file.arrayBuffer());
  const sourceWidth = decoded.width;
  const sourceHeight = decoded.height;
  if (!Number.isInteger(sourceWidth) || !Number.isInteger(sourceHeight) || sourceWidth < 1 || sourceHeight < 1) {
    throw new UserImageNormalizationError("heif_decode_failed");
  }

  const pixels = new Uint8ClampedArray(decoded.data);
  if (pixels.length !== sourceWidth * sourceHeight * 4) {
    throw new UserImageNormalizationError("heif_decode_failed");
  }
  const scale = Math.min(1, Math.sqrt(maximumPixelCount / (sourceWidth * sourceHeight)));
  const width = Math.max(1, Math.round(sourceWidth * scale));
  const height = Math.max(1, Math.round(sourceHeight * scale));
  const sourceCanvas = document.createElement("canvas");
  sourceCanvas.width = sourceWidth;
  sourceCanvas.height = sourceHeight;
  const sourceContext = sourceCanvas.getContext("2d");
  if (sourceContext === null) throw new UserImageNormalizationError("heif_decode_failed");
  sourceContext.putImageData(new ImageData(pixels, sourceWidth, sourceHeight), 0, 0);

  const outputCanvas = width === sourceWidth && height === sourceHeight
    ? sourceCanvas
    : document.createElement("canvas");
  outputCanvas.width = width;
  outputCanvas.height = height;
  if (outputCanvas !== sourceCanvas) {
    const outputContext = outputCanvas.getContext("2d");
    if (outputContext === null) throw new UserImageNormalizationError("heif_decode_failed");
    outputContext.drawImage(sourceCanvas, 0, 0, width, height);
  }
  try {
    return await canvasToJpeg(outputCanvas);
  } finally {
    sourceCanvas.width = 0;
    sourceCanvas.height = 0;
    if (outputCanvas !== sourceCanvas) {
      outputCanvas.width = 0;
      outputCanvas.height = 0;
    }
  }
}

function canvasToJpeg(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => {
      if (value === null) reject(new UserImageNormalizationError("heif_decode_failed"));
      else resolve(value);
    }, "image/jpeg", 0.9);
  });
}

function loadImage(sourceUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new UserImageNormalizationError("heif_decode_failed"));
    image.src = sourceUrl;
  });
}

function jpegFileName(name: string): string {
  const baseName = name.replace(/\.[^.]+$/, "").trim() || "image";
  return `${baseName}.jpg`;
}
