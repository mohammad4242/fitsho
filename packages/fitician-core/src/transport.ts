export type JsonPrimitive = string | number | boolean | null;

export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];

export type JsonObject = {
  readonly [key: string]: JsonValue;
};

export type HttpMethod = "DELETE" | "GET" | "PATCH" | "POST" | "PUT";

export type RequestHeaders = Readonly<Record<string, string>>;

export interface CancellationSignal {
  readonly aborted: boolean;
}

export interface TransportRequest {
  readonly path: string;
  readonly method?: HttpMethod;
  readonly headers?: RequestHeaders;
  readonly query?: Readonly<Record<string, boolean | number | string | null | undefined>>;
  readonly body?: JsonValue;
  readonly signal?: CancellationSignal;
}

export interface ApiValidationDetail {
  readonly type?: string;
  readonly loc?: readonly (string | number)[];
  readonly msg?: string;
}

export interface ApiErrorObject {
  readonly code?: string;
  readonly message?: string;
  readonly [key: string]: JsonValue | undefined;
}

export interface ApiErrorPayload {
  readonly detail?: ApiErrorObject | ApiValidationDetail[] | string | null;
}

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

export interface Page<TItem> {
  readonly items: readonly TItem[];
  readonly page: number;
  readonly pageSize: number;
  readonly total: number;
}

export interface CursorPage<TItem> {
  readonly items: readonly TItem[];
  readonly next: string | null;
  readonly previous: string | null;
}

export interface BinaryDownload {
  readonly bytes: Uint8Array;
  readonly contentType: string | null;
  readonly filename: string | null;
}

export interface BinaryDownloadRequest extends TransportRequest {
  readonly responseType: "binary";
}

export interface MultipartPart {
  readonly name: string;
  readonly bytes?: Uint8Array;
  readonly value?: string;
  readonly filename?: string;
  readonly contentType?: string;
}

export interface MultipartUploadRequest extends Omit<TransportRequest, "body"> {
  readonly parts: readonly MultipartPart[];
}

export interface FiticianTransport {
  request<TResponse>(request: TransportRequest): Promise<TResponse>;
  download(request: BinaryDownloadRequest): Promise<BinaryDownload>;
  upload<TResponse>(request: MultipartUploadRequest): Promise<TResponse>;
}
