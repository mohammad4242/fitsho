import type {
  ApiError,
  BinaryDownload,
  FiticianTransport,
  MultipartUploadRequest,
  Page,
} from "./transport";

const page: Page<{ id: string }> = {
  items: [{ id: "item-1" }],
  page: 1,
  pageSize: 20,
  total: 1,
};

const binary: BinaryDownload = {
  bytes: new Uint8Array(),
  contentType: "application/pdf",
  filename: "plan.pdf",
};

const upload: MultipartUploadRequest = {
  path: "/api/v1/upload",
  method: "POST",
  parts: [{ name: "file", bytes: new Uint8Array(), filename: "photo.jpg" }],
};

const transport: FiticianTransport = {
  request: async <T>() => ({}) as T,
  download: async () => binary,
  upload: async <T>() => ({}) as T,
};

const error: ApiError = new Error("contract placeholder") as ApiError;

void page;
void transport;
void upload;
void error;
