export const FITICIAN_CORE_VERSION = "0.1.0";

export type { components, paths, webhooks } from "./generated/api";
export { ApiError } from "./transport";
export type {
  ApiErrorObject,
  ApiErrorPayload,
  ApiValidationDetail,
  BinaryDownload,
  BinaryDownloadRequest,
  CancellationSignal,
  CursorPage,
  FiticianTransport,
  HttpMethod,
  JsonObject,
  JsonPrimitive,
  JsonValue,
  MultipartPart,
  MultipartUploadRequest,
  Page,
  RequestHeaders,
  TransportRequest,
} from "./transport";
