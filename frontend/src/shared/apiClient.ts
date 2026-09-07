import {
  type HttpMethod,
  type JsonValue,
  type RequestHeaders,
} from "@fitician/core";

import { createWebTransport } from "./webTransport";

export { ApiError } from "@fitician/core";
export type { ApiValidationDetail } from "@fitician/core";

const browserTransport = createWebTransport();

function isFormDataBody(body: BodyInit | null | undefined): body is FormData {
  return typeof FormData !== "undefined" && body instanceof FormData;
}

function requestMethod(method: string | undefined): HttpMethod {
  const normalized = (method ?? "GET").toUpperCase();
  if (normalized === "DELETE" || normalized === "GET" || normalized === "PATCH"
    || normalized === "POST" || normalized === "PUT") {
    return normalized;
  }
  throw new TypeError(`Unsupported HTTP method: ${method}`);
}

function requestHeaders(init: RequestInit | undefined, isMultipart: boolean): RequestHeaders {
  const headers = new Headers(init?.headers);
  if (!isMultipart && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return Object.fromEntries(headers.entries());
}

function requestBody(body: BodyInit | null | undefined): JsonValue | undefined {
  if (body === undefined || body === null) {
    return undefined;
  }
  if (typeof body !== "string") {
    throw new TypeError("Only JSON strings and FormData are supported by the web API client");
  }
  try {
    return JSON.parse(body) as JsonValue;
  } catch {
    throw new TypeError("The web API client requires a valid JSON request body");
  }
}

function requestOptions(init: RequestInit | undefined, isMultipart: boolean) {
  return {
    headers: requestHeaders(init, isMultipart),
    method: requestMethod(init?.method),
    signal: init?.signal ?? undefined,
  };
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (isFormDataBody(init?.body)) {
    return browserTransport.uploadFormData<T>({
      ...requestOptions(init, true),
      formData: init.body,
      path,
    });
  }
  return browserTransport.request<T>({
    ...requestOptions(init, false),
    body: requestBody(init?.body),
    path,
  });
}

export async function requestBlob(path: string, init?: RequestInit): Promise<Blob> {
  const download = await browserTransport.download({
    ...requestOptions(init, false),
    body: requestBody(init?.body),
    path,
    responseType: "binary",
  });
  return new Blob([download.bytes.buffer as ArrayBuffer], {
    type: download.contentType ?? "",
  });
}
