import type {
  BinaryDownload,
  BinaryDownloadRequest,
} from "@fitician/core";

type AuthenticatedBinaryClient = {
  download(request: BinaryDownloadRequest): Promise<BinaryDownload>;
};

export type StoredPrivateMediaFile = {
  readonly userId: string;
  readonly fileName: string;
  readonly uri: string;
  readonly contentType: string;
  readonly byteSize: number;
};

export interface PrivateMediaStorage {
  save(userId: string, fileName: string, download: BinaryDownload): Promise<StoredPrivateMediaFile>;
  clearUserFiles(userId: string): Promise<void>;
}

export type PrivateMediaDownloadRequest = Pick<BinaryDownloadRequest, "path" | "query"> & {
  readonly fileName: string;
};

export interface PrivateMediaClientOptions {
  readonly authClient: AuthenticatedBinaryClient;
  readonly storage: PrivateMediaStorage;
  readonly userId: string;
}

export class PrivateMediaError extends Error {
  readonly code = "INVALID_PRIVATE_MEDIA";

  constructor(message: string) {
    super(message);
    this.name = "PrivateMediaError";
  }
}

export function validatePrivateMediaUserId(userId: string): string {
  if (
    userId.length === 0 ||
    userId.length > 200 ||
    /[\u0000-\u001f\u007f]/u.test(userId)
  ) {
    throw new PrivateMediaError("A valid private media user id is required");
  }
  return userId;
}

export function validatePrivateMediaFileName(fileName: string): string {
  if (
    fileName.length === 0 ||
    fileName.length > 160 ||
    fileName === "." ||
    fileName === ".." ||
    !/^[A-Za-z0-9][A-Za-z0-9._-]*$/u.test(fileName)
  ) {
    throw new PrivateMediaError("Private media filenames must be safe and non-empty");
  }
  return fileName;
}

function validatePrivateMediaPath(path: string): string {
  const normalizedPath = path.trim();
  if (
    normalizedPath.length === 0 ||
    !normalizedPath.startsWith("/") ||
    /[\u0000-\u001f\u007f]/u.test(normalizedPath)
  ) {
    throw new PrivateMediaError("A private media API path is required");
  }
  return normalizedPath;
}

export class PrivateMediaClient {
  private readonly authClient: AuthenticatedBinaryClient;
  private readonly storage: PrivateMediaStorage;
  private readonly userId: string;

  constructor(options: PrivateMediaClientOptions) {
    this.authClient = options.authClient;
    this.storage = options.storage;
    this.userId = validatePrivateMediaUserId(options.userId);
  }

  async download(request: PrivateMediaDownloadRequest): Promise<StoredPrivateMediaFile> {
    const fileName = validatePrivateMediaFileName(request.fileName);
    const response = await this.authClient.download({
      headers: {
        "Cache-Control": "no-store",
        Pragma: "no-cache",
      },
      method: "GET",
      path: validatePrivateMediaPath(request.path),
      query: request.query,
      responseType: "binary",
    });
    if (response.bytes.byteLength === 0) {
      throw new PrivateMediaError("Private media response was empty");
    }
    return this.storage.save(this.userId, fileName, response);
  }

  async clearUserFiles(): Promise<void> {
    await this.storage.clearUserFiles(this.userId);
  }
}
