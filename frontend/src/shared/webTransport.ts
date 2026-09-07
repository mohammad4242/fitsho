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

export type FetchLike = typeof fetch;

export interface WebFiticianTransport extends FiticianTransport {
  uploadFormData<TResponse>(
    request: Omit<MultipartUploadRequest, "parts"> & { formData: FormData },
  ): Promise<TResponse>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function requestBody(body: TransportRequest["body"]): BodyInit | undefined {
  return body === undefined ? undefined : JSON.stringify(body);
}

function requestHeaders(
  headers: TransportRequest["headers"],
  isMultipart: boolean,
): Headers {
  const result = new Headers(headers);
  if (!isMultipart && !result.has("Content-Type")) {
    result.set("Content-Type", "application/json");
  }
  return result;
}

function requestInit(
  request: TransportRequest,
  body: BodyInit | undefined,
  isMultipart = false,
): RequestInit {
  return {
    body,
    credentials: "include",
    headers: requestHeaders(request.headers, isMultipart),
    method: request.method ?? "GET",
    signal: request.signal as AbortSignal | undefined,
  };
}

async function throwForError(response: Response): Promise<never> {
  const body = (await response.json().catch(() => null)) as {
    detail?: unknown;
  } | null;
  const detail = body?.detail;
  const message = typeof detail === "string" ? detail : "Request failed";
  const details = Array.isArray(detail) ? (detail as ApiValidationDetail[]) : null;
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
  return new Blob([part.bytes?.buffer as ArrayBuffer], {
    type: part.contentType ?? "application/octet-stream",
  });
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

export async function formDataToMultipart(formData: FormData): Promise<MultipartPart[]> {
  const entries: Array<[string, FormDataEntryValue]> = [];
  formData.forEach((value, name) => entries.push([name, value]));
  return Promise.all(
    entries.map(async ([name, value]) => {
      if (typeof value === "string") {
        return { name, value };
      }
      return {
        bytes: new Uint8Array(await value.arrayBuffer()),
        contentType: value.type || undefined,
        filename: value.name,
        name,
      };
    }),
  );
}

export function createWebTransport(fetchImpl?: FetchLike): WebFiticianTransport {
  const fetchRequest: FetchLike = fetchImpl ?? ((input, init) => globalThis.fetch(input, init));

  return {
    async request<TResponse>(request: TransportRequest): Promise<TResponse> {
      const response = await fetchRequest(
        request.path,
        requestInit(request, requestBody(request.body)),
      );
      await ensureOk(response);
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },

    async download(request: BinaryDownloadRequest): Promise<BinaryDownload> {
      const response = await fetchRequest(
        request.path,
        requestInit(request, requestBody(request.body)),
      );
      await ensureOk(response);
      return {
        bytes: new Uint8Array(await response.arrayBuffer()),
        contentType: response.headers.get("Content-Type"),
        filename: responseFilename(response),
      };
    },

    async upload<TResponse>(request: MultipartUploadRequest): Promise<TResponse> {
      const response = await fetchRequest(
        request.path,
        requestInit(request, multipartFormData(request.parts), true),
      );
      await ensureOk(response);
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },

    async uploadFormData<TResponse>(
      request: Omit<MultipartUploadRequest, "parts"> & { formData: FormData },
    ): Promise<TResponse> {
      const response = await fetchRequest(
        request.path,
        requestInit(request, request.formData, true),
      );
      await ensureOk(response);
      if (response.status === 204) {
        return undefined as TResponse;
      }
      return (await response.json()) as TResponse;
    },
  };
}
