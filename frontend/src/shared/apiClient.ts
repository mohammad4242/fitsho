export type ApiValidationDetail = {
  type?: string;
  loc?: Array<string | number>;
  msg?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly details: ApiValidationDetail[] | null;

  constructor(
    status: number,
    message: string,
    details: ApiValidationDetail[] | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
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
    throw new ApiError(response.status, message, details);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
