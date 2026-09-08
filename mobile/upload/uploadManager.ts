import { randomUUID } from "expo-crypto";
import {
  ApiError,
  type CancellationSignal,
  type FiticianTransport,
  type HttpMethod,
  type MultipartPart,
  type MultipartUploadRequest,
  type RequestHeaders,
} from "@fitician/core";
import { onlineManager } from "@tanstack/react-query";
import {
  mobilePerformanceRecorder,
  type MobilePerformanceRecorder,
} from "../platform/performance";

const DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const RETRYABLE_API_STATUSES = new Set([408, 425, 429]);
const QUEUEABLE_OPERATIONS = new Set<UploadOperation>(["tracking", "check-in"]);

export type UploadOperation =
  | "tracking"
  | "check-in"
  | "photo"
  | "medical"
  | "consent"
  | "plan-edit"
  | "other";

export type UploadJob = {
  readonly id?: string;
  readonly operation: UploadOperation;
  readonly path: string;
  readonly method?: HttpMethod;
  readonly headers?: RequestHeaders;
  readonly parts: readonly MultipartPart[];
  readonly allowedContentTypes?: readonly string[];
  readonly maxBytes?: number;
  readonly idempotencyKey?: string;
};

export type UploadStatus = "queued" | "uploading" | "completed" | "cancelled" | "failed";

export type UploadProgress = {
  readonly jobId: string;
  readonly status: UploadStatus;
  readonly loadedBytes: number;
  readonly totalBytes: number;
  readonly fraction: number;
};

export type UploadProgressReporter = (loadedBytes: number) => void;

export type UploadExecutor = <TResponse>(
  request: MultipartUploadRequest,
  reportProgress: UploadProgressReporter,
  signal: CancellationSignal,
) => Promise<TResponse>;

export type UploadHandle<TResponse> = {
  readonly id: string;
  readonly idempotencyKey: string;
  readonly promise: Promise<TResponse>;
  readonly cancel: () => void;
  readonly getSnapshot: () => UploadProgress;
};

export interface UploadManagerOptions {
  executor: UploadExecutor;
  isOnline?: () => boolean;
  idempotencyKeyFactory?: () => string;
  onProgress?: (progress: UploadProgress) => void;
  performanceRecorder?: MobilePerformanceRecorder;
}

export class UploadValidationError extends Error {
  readonly code = "INVALID_UPLOAD";

  constructor(message: string) {
    super(message);
    this.name = "UploadValidationError";
  }
}

export class OfflineUploadError extends Error {
  readonly code = "OFFLINE_UPLOAD_NOT_QUEUEABLE";

  constructor(operation: UploadOperation) {
    super(`The ${operation} upload cannot be queued while offline`);
    this.name = "OfflineUploadError";
  }
}

export class UploadCancellationError extends Error {
  readonly code = "UPLOAD_CANCELLED";

  constructor() {
    super("Upload was cancelled");
    this.name = "UploadCancellationError";
  }
}

export function isQueueableUploadOperation(operation: UploadOperation): boolean {
  return QUEUEABLE_OPERATIONS.has(operation);
}

export function validateUploadJob(job: UploadJob): number {
  if (job.path.trim().length === 0) {
    throw new UploadValidationError("An upload path is required");
  }
  if (job.parts.length === 0) {
    throw new UploadValidationError("An upload requires at least one non-empty file");
  }
  if (job.maxBytes !== undefined && (!Number.isSafeInteger(job.maxBytes) || job.maxBytes <= 0)) {
    throw new UploadValidationError("Upload size limit must be a positive integer");
  }

  const maxBytes = job.maxBytes ?? DEFAULT_MAX_UPLOAD_BYTES;
  const allowedContentTypes = new Set(job.allowedContentTypes ?? []);
  let totalBytes = 0;
  let hasFile = false;

  for (const part of job.parts) {
    const hasBytes = part.bytes !== undefined;
    const hasValue = part.value !== undefined;
    if (hasBytes === hasValue) {
      throw new UploadValidationError("Each multipart part must contain exactly one value");
    }
    if (hasValue) {
      continue;
    }

    hasFile = true;
    if (part.bytes === undefined || part.bytes.length === 0) {
      throw new UploadValidationError("An upload requires at least one non-empty file");
    }
    if (
      part.filename === undefined ||
      part.filename.length === 0 ||
      /[\u0000-\u001f\u007f/\\]/u.test(part.filename)
    ) {
      throw new UploadValidationError("Uploaded filenames must be safe and non-empty");
    }
    if (part.contentType === undefined || part.contentType.length === 0) {
      throw new UploadValidationError("Uploaded files require a content type");
    }
    if (allowedContentTypes.size > 0 && !allowedContentTypes.has(part.contentType)) {
      throw new UploadValidationError(`Unsupported upload content type: ${part.contentType}`);
    }
    totalBytes += part.bytes.length;
    if (totalBytes > maxBytes) {
      throw new UploadValidationError("Upload exceeds its size limit");
    }
  }

  if (!hasFile) {
    throw new UploadValidationError("An upload requires at least one non-empty file");
  }
  return totalBytes;
}

function validateIdempotencyKey(idempotencyKey: string): void {
  if (
    idempotencyKey.length < 8 ||
    idempotencyKey.length > 128 ||
    /[\u0000-\u001f\u007f\s]/u.test(idempotencyKey)
  ) {
    throw new UploadValidationError("Idempotency keys must be 8-128 non-whitespace characters");
  }
}

function isRetryableUploadError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status >= 500 || RETRYABLE_API_STATUSES.has(error.status);
  }
  return true;
}

class UploadCancellationController {
  private cancelled = false;
  readonly signal: CancellationSignal;

  constructor() {
    const owner = this;
    this.signal = {
      get aborted() {
        return owner.cancelled;
      },
    };
  }

  cancel(): void {
    this.cancelled = true;
  }
}

type UploadEntry<TResponse> = {
  readonly job: UploadJob;
  readonly id: string;
  readonly idempotencyKey: string;
  readonly totalBytes: number;
  readonly cancellation: UploadCancellationController;
  readonly promise: Promise<TResponse>;
  readonly resolve: (value: TResponse) => void;
  readonly reject: (reason?: unknown) => void;
  status: UploadStatus;
  loadedBytes: number;
};

export class UploadManager {
  private readonly executor: UploadExecutor;
  private readonly isOnline: () => boolean;
  private readonly idempotencyKeyFactory: () => string;
  private readonly onProgress: ((progress: UploadProgress) => void) | undefined;
  private readonly performanceRecorder: MobilePerformanceRecorder;
  private readonly entries = new Map<string, UploadEntry<unknown>>();

  constructor(options: UploadManagerOptions) {
    this.executor = options.executor;
    this.isOnline = options.isOnline ?? (() => onlineManager.isOnline());
    this.idempotencyKeyFactory = options.idempotencyKeyFactory ?? randomUUID;
    this.onProgress = options.onProgress;
    this.performanceRecorder = options.performanceRecorder ?? mobilePerformanceRecorder;
  }

  enqueue<TResponse>(job: UploadJob): UploadHandle<TResponse> {
    const totalBytes = validateUploadJob(job);
    const idempotencyKey = job.idempotencyKey ?? this.idempotencyKeyFactory();
    validateIdempotencyKey(idempotencyKey);

    const existing = this.entries.get(idempotencyKey);
    if (existing !== undefined) {
      return this.createHandle(existing as UploadEntry<TResponse>);
    }
    if (!this.isOnline() && !isQueueableUploadOperation(job.operation)) {
      throw new OfflineUploadError(job.operation);
    }

    let resolvePromise!: (value: TResponse) => void;
    let rejectPromise!: (reason?: unknown) => void;
    const entry: UploadEntry<TResponse> = {
      cancellation: new UploadCancellationController(),
      id: job.id ?? idempotencyKey,
      idempotencyKey,
      job,
      loadedBytes: 0,
      promise: new Promise<TResponse>((resolve, reject) => {
        resolvePromise = resolve;
        rejectPromise = reject;
      }),
      reject: rejectPromise,
      resolve: resolvePromise,
      status: "queued",
      totalBytes,
    };
    this.entries.set(idempotencyKey, entry as UploadEntry<unknown>);
    this.emit(entry);
    if (this.isOnline()) {
      void this.run(entry);
    }
    return this.createHandle(entry);
  }

  async reconnect(): Promise<void> {
    if (!this.isOnline()) {
      return;
    }
    const queued = [...this.entries.values()].filter((entry) => entry.status === "queued");
    await Promise.all(queued.map((entry) => this.run(entry)));
  }

  private createHandle<TResponse>(entry: UploadEntry<TResponse>): UploadHandle<TResponse> {
    return {
      cancel: () => this.cancel(entry),
      getSnapshot: () => this.snapshot(entry),
      id: entry.id,
      idempotencyKey: entry.idempotencyKey,
      promise: entry.promise,
    };
  }

  private snapshot<TResponse>(entry: UploadEntry<TResponse>): UploadProgress {
    return {
      fraction: entry.totalBytes === 0 ? 0 : entry.loadedBytes / entry.totalBytes,
      jobId: entry.id,
      loadedBytes: entry.loadedBytes,
      status: entry.status,
      totalBytes: entry.totalBytes,
    };
  }

  private emit<TResponse>(entry: UploadEntry<TResponse>): void {
    this.onProgress?.(this.snapshot(entry));
  }

  private cancel<TResponse>(entry: UploadEntry<TResponse>): void {
    if (entry.status === "completed" || entry.status === "failed" || entry.status === "cancelled") {
      return;
    }
    entry.cancellation.cancel();
    if (entry.status === "queued") {
      entry.status = "cancelled";
      this.entries.delete(entry.idempotencyKey);
      this.emit(entry);
      entry.reject(new UploadCancellationError());
    }
  }

  private async run<TResponse>(entry: UploadEntry<TResponse>): Promise<void> {
    if (entry.status !== "queued" || entry.cancellation.signal.aborted || !this.isOnline()) {
      return;
    }
    entry.status = "uploading";
    this.emit(entry);
    const request: MultipartUploadRequest = {
      headers: {
        ...Object.fromEntries(
          Object.entries(entry.job.headers ?? {}).filter(
            ([name]) => name.toLowerCase() !== "idempotency-key",
          ),
        ),
        "Idempotency-Key": entry.idempotencyKey,
      },
      method: entry.job.method ?? "POST",
      parts: entry.job.parts,
      path: entry.job.path,
      signal: entry.cancellation.signal,
    };

    const completeUploadMeasurement = this.performanceRecorder.start("upload");
    try {
      const response = await this.executor<TResponse>(
        request,
        (loadedBytes) => {
          entry.loadedBytes = Math.min(Math.max(loadedBytes, 0), entry.totalBytes);
          this.emit(entry);
        },
        entry.cancellation.signal,
      );
      if (entry.cancellation.signal.aborted) {
        throw new UploadCancellationError();
      }
      entry.loadedBytes = entry.totalBytes;
      entry.status = "completed";
      this.entries.delete(entry.idempotencyKey);
      this.emit(entry);
      entry.resolve(response);
    } catch (error) {
      if (entry.cancellation.signal.aborted || error instanceof UploadCancellationError) {
        entry.status = "cancelled";
        this.entries.delete(entry.idempotencyKey);
        this.emit(entry);
        entry.reject(new UploadCancellationError());
        return;
      }
      if (isQueueableUploadOperation(entry.job.operation) && isRetryableUploadError(error)) {
        entry.status = "queued";
        this.emit(entry);
        return;
      }
      entry.status = "failed";
      this.entries.delete(entry.idempotencyKey);
      this.emit(entry);
      entry.reject(error);
    } finally {
      completeUploadMeasurement();
    }
  }
}

export function createTransportUploadExecutor(transport: FiticianTransport): UploadExecutor {
  return async <TResponse>(
    request: MultipartUploadRequest,
    reportProgress: UploadProgressReporter,
    signal: CancellationSignal,
  ): Promise<TResponse> => {
    const totalBytes = request.parts.reduce(
      (total, part) => total + (part.bytes?.length ?? 0),
      0,
    );
    if (signal.aborted) {
      throw new UploadCancellationError();
    }
    reportProgress(0);
    const response = await transport.upload<TResponse>({ ...request, signal });
    if (signal.aborted) {
      throw new UploadCancellationError();
    }
    reportProgress(totalBytes);
    return response;
  };
}
