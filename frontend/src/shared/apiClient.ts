export type ApiValidationDetail = {
  type?: string;
  loc?: Array<string | number>;
  msg?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly details: ApiValidationDetail[] | null;
  readonly code: string | null;

  constructor(
    status: number,
    message: string,
    details: ApiValidationDetail[] | null = null,
    code: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
    this.code = code;
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    const message = typeof body?.detail === "string" ? body.detail : "Request failed";
    const details = Array.isArray(body?.detail)
      ? (body.detail as ApiValidationDetail[])
      : null;
    const code = typeof body?.detail === "object" && body.detail !== null
      && "code" in body.detail && typeof body.detail.code === "string"
      ? body.detail.code
      : null;
    throw new ApiError(response.status, message, details, code);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
