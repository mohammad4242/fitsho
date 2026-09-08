import {
  ApiError,
  type ApiValidationDetail,
  type BinaryDownload,
  type BinaryDownloadRequest,
  type FiticianTransport,
  type MultipartPart,
  type MultipartUploadRequest,
  type TransportRequest,
} from "@fitician/core";
import {
  CORRELATION_ID_HEADER,
  createCorrelationId,
  mobileLogger,
  type MobileLogger,
} from "../platform/logging";

export type NativeFetchLike = typeof fetch;

export interface NativeTransportOptions {
  readonly apiBaseUrl: string;
  readonly correlationIdFactory?: () => string;
  readonly fetchImpl?: NativeFetchLike;
  readonly logger?: MobileLogger;
  readonly trustedOrigin?: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requestUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function requestBody(body: TransportRequest["body"]): string | undefined {
  return body === undefined ? undefined : JSON.stringify(body);
}

function requestHeaders(
  headers: TransportRequest["headers"],
  trustedOrigin: string | null | undefined,
  correlationId: string,
  isMultipart: boolean,
): Headers {
  const result = new Headers(headers);
  if (trustedOrigin !== undefined && trustedOrigin !== null && !result.has("Origin")) {
    result.set("Origin", trustedOrigin);
  }
  if (!isMultipart && !result.has("Content-Type")) {
    result.set("Content-Type", "application/json");
  }
  if (!result.has(CORRELATION_ID_HEADER)) {
    result.set(CORRELATION_ID_HEADER, correlationId);
  }
  return result;
}

function requestInit(
  request: TransportRequest,
  body: BodyInit | undefined,
  trustedOrigin: string | null | undefined,
  correlationId: string,
  isMultipart = false,
): RequestInit {
  return {
    body,
    headers: requestHeaders(request.headers, trustedOrigin, correlationId, isMultipart),
    method: request.method ?? "GET",
    signal: request.signal as AbortSignal | undefined,
  };
}

async function throwForError(response: Response): Promise<never> {
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = body?.detail;
  const details = Array.isArray(detail) ? (detail as ApiValidationDetail[]) : null;
  const message = typeof detail === "string"
    ? detail
    : isRecord(detail) && typeof detail.message === "string"
      ? detail.message
      : "Request failed";
  const code = isRecord(detail) && typeof detail.code === "string" ? detail.code : null;
  throw new ApiError(response.status, message, details, code);
}

async function ensureOk(response: Response): Promise<Response> {
  if (!response.ok) {
    await throwForError(response);
  }
  return response;
}

function responseFilename(response: Response): string | null {
  const contentDisposition = response.headers.get("Content-Disposition");
  if (!contentDisposition) {
    return null;
  }
  const match = /filename\*=(?:UTF-8'')?([^;]+)|filename="?([^";]+)"?/i.exec(
    contentDisposition,
  );
  const filename = match?.[1] ?? match?.[2];
  if (!filename) {
    return null;
  }
  try {
    return decodeURIComponent(filename);
  } catch {
    return filename;
  }
}

function bytesToBlob(part: MultipartPart): Blob {
  const bytes = part.bytes as Uint8Array;
  const buffer = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
  return new Blob([buffer], { type: part.contentType ?? "application/octet-stream" });
}

function multipartFormData(parts: readonly MultipartPart[]): FormData {
  const formData = new FormData();
  for (const part of parts) {
    if (part.bytes !== undefined) {
      const blob = bytesToBlob(part);
      if (part.filename !== undefined) {
        formData.append(part.name, blob, part.filename);
      } else {
        formData.append(part.name, blob);
      }
    } else {
      formData.append(part.name, part.value ?? "");
    }
  }
  return formData;
}

export function createNativeTransport(options: NativeTransportOptions): FiticianTransport {
  const fetchRequest = options.fetchImpl ?? ((input, init) => globalThis.fetch(input, init));
  const logger = options.logger ?? mobileLogger;
  const correlationIdFactory = options.correlationIdFactory ?? createCorrelationId;

  async function send(
    request: TransportRequest,
    body: BodyInit | undefined,
    operation: "request" | "download" | "upload",
    isMultipart = false,
  ): Promise<Response> {
    const correlationId = correlationIdFactory();
    const startedAt = Date.now();
    let response: Response | undefined;
    try {
      response = await fetchRequest(
        requestUrl(options.apiBaseUrl, request.path),
        requestInit(request, body, options.trustedOrigin, correlationId, isMultipart),
      );
      await ensureOk(response);
      logger.captureMessage("native_request_completed", "info", {
        correlation_id: correlationId,
        duration_ms: Date.now() - startedAt,
        http_status: response.status,
        method: request.method ?? "GET",
        operation,
      });
      return response;
    } catch (error) {
      logger.captureException("native_request_failed", error, {
        correlation_id: correlationId,
        duration_ms: Date.now() - startedAt,
        http_status: response?.status ?? null,
        method: request.method ?? "GET",
        operation,
      });
      throw error;
    }
  }

  return {
    async request<TResponse>(request: TransportRequest): Promise<TResponse> {
      const response = await send(request, requestBody(request.body), "request");
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },

    async download(request: BinaryDownloadRequest): Promise<BinaryDownload> {
      const response = await send(request, requestBody(request.body), "download");
      return {
        bytes: new Uint8Array(await response.arrayBuffer()),
        contentType: response.headers.get("Content-Type"),
        filename: responseFilename(response),
      };
    },

    async upload<TResponse>(request: MultipartUploadRequest): Promise<TResponse> {
      const response = await send(
        request,
        multipartFormData(request.parts),
        "upload",
        true,
      );
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },
  };
}
