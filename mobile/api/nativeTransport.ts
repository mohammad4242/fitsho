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

type PreparedMultipartBody = {
  readonly body: Uint8Array;
  readonly contentType: string;
};

let multipartBoundarySequence = 0;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requestUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) {
    throw new Error("Native API request paths must be relative to the configured backend");
  }
  return `${baseUrl.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function requestBody(body: TransportRequest["body"]): string | undefined {
  return body === undefined ? undefined : JSON.stringify(body);
}

function nativeAbortSignal(signal: TransportRequest["signal"]): AbortSignal | undefined {
  if (signal === undefined || typeof AbortSignal === "undefined") return undefined;
  return signal instanceof AbortSignal ? signal : undefined;
}

function requestHeaders(
  headers: TransportRequest["headers"],
  trustedOrigin: string | null | undefined,
  correlationId: string,
  contentType: string | null,
): Headers {
  const result = new Headers(headers);
  if (trustedOrigin !== undefined && trustedOrigin !== null && !result.has("Origin")) {
    result.set("Origin", trustedOrigin);
  }
  if (!result.has("Content-Type")) {
    result.set("Content-Type", contentType ?? "application/json");
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
  contentType: string | null = null,
): RequestInit {
  return {
    body,
    headers: requestHeaders(request.headers, trustedOrigin, correlationId, contentType),
    method: request.method ?? "GET",
    signal: nativeAbortSignal(request.signal),
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

function multipartQuotedValue(value: string): string {
  return value.replace(/["\r\n]/gu, "_");
}

function joinBytes(chunks: readonly Uint8Array[]): Uint8Array {
  const result = new Uint8Array(chunks.reduce((total, chunk) => total + chunk.byteLength, 0));
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}

function utf8Bytes(value: string): Uint8Array {
  const bytes: number[] = [];
  for (const character of value) {
    const codePoint = character.codePointAt(0) ?? 0xfffd;
    if (codePoint <= 0x7f) {
      bytes.push(codePoint);
    } else if (codePoint <= 0x7ff) {
      bytes.push(0xc0 | (codePoint >> 6), 0x80 | (codePoint & 0x3f));
    } else if (codePoint <= 0xffff) {
      bytes.push(
        0xe0 | (codePoint >> 12),
        0x80 | ((codePoint >> 6) & 0x3f),
        0x80 | (codePoint & 0x3f),
      );
    } else {
      bytes.push(
        0xf0 | (codePoint >> 18),
        0x80 | ((codePoint >> 12) & 0x3f),
        0x80 | ((codePoint >> 6) & 0x3f),
        0x80 | (codePoint & 0x3f),
      );
    }
  }
  return Uint8Array.from(bytes);
}

function multipartBody(parts: readonly MultipartPart[]): PreparedMultipartBody {
  const boundary = `----FiticianBoundary${Date.now().toString(36)}${multipartBoundarySequence++}`;
  const chunks: Uint8Array[] = [];
  for (const part of parts) {
    const disposition = `Content-Disposition: form-data; name="${multipartQuotedValue(part.name)}"`;
    chunks.push(utf8Bytes(`--${boundary}\r\n`));
    if (part.bytes !== undefined) {
      const filename = multipartQuotedValue(part.filename ?? "upload.bin");
      const contentType = part.contentType ?? "application/octet-stream";
      chunks.push(utf8Bytes(
        `${disposition}; filename="${filename}"\r\nContent-Type: ${contentType}\r\n\r\n`,
      ));
      chunks.push(part.bytes as Uint8Array);
    } else {
      chunks.push(utf8Bytes(`${disposition}\r\n\r\n${part.value ?? ""}`));
    }
    chunks.push(utf8Bytes("\r\n"));
  }
  chunks.push(utf8Bytes(`--${boundary}--\r\n`));
  return {
    body: joinBytes(chunks),
    contentType: `multipart/form-data; boundary=${boundary}`,
  };
}

export function createNativeTransport(options: NativeTransportOptions): FiticianTransport {
  const fetchRequest = options.fetchImpl ?? ((input, init) => globalThis.fetch(input, init));
  const logger = options.logger ?? mobileLogger;
  const correlationIdFactory = options.correlationIdFactory ?? createCorrelationId;

  async function send(
    request: TransportRequest,
    body: BodyInit | undefined,
    operation: "request" | "download" | "upload",
    contentType: string | null = null,
  ): Promise<Response> {
    const correlationId = correlationIdFactory();
    const startedAt = Date.now();
    let response: Response | undefined;
    try {
      response = await fetchRequest(
        requestUrl(options.apiBaseUrl, request.path),
        requestInit(request, body, options.trustedOrigin, correlationId, contentType),
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
      const prepared = multipartBody(request.parts);
      const response = await send(
        request,
        prepared.body as unknown as BodyInit,
        "upload",
        prepared.contentType,
      );
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },
  };
}
