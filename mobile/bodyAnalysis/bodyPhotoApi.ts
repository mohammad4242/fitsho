import { File } from "expo-file-system";
import type {
  BodyAnalysis,
  BodyPhotoPurpose,
  BodyPhotoSession,
  BodyPhotoSessionList,
  BodyPhotoView,
  BodyProgressComparison,
  BodyProgressTimelineResponse,
} from "@fitician/core/body-photos";
import type {
  BinaryDownload,
  BinaryDownloadRequest,
  MultipartUploadRequest,
  TransportRequest,
} from "@fitician/core";

import type { BodyPhotoCapturedAsset } from "./cameraCapture";

export type AuthenticatedBodyPhotoRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export type AuthenticatedBodyPhotoUpload = <TResponse>(
  request: MultipartUploadRequest,
) => Promise<TResponse>;

export type AuthenticatedBodyPhotoDownload = (
  request: BinaryDownloadRequest,
) => Promise<BinaryDownload>;

export interface BodyPhotoApi {
  createSession(purpose: BodyPhotoPurpose): Promise<BodyPhotoSession>;
  deleteSession(sessionId: string): Promise<void>;
  downloadPhoto(sessionId: string, view: BodyPhotoView): Promise<BinaryDownload>;
  getAnalysis(sessionId: string): Promise<BodyAnalysis | null>;
  getComparison(sessionId: string): Promise<BodyProgressComparison | null>;
  getSession(sessionId: string): Promise<BodyPhotoSession>;
  getTimeline(): Promise<BodyProgressTimelineResponse>;
  listSessions(): Promise<BodyPhotoSessionList>;
  retryAnalysis(sessionId: string, confirmMeasurementsCurrent?: boolean): Promise<BodyAnalysis>;
  startAnalysis(sessionId: string, confirmMeasurementsCurrent?: boolean): Promise<BodyAnalysis>;
  submitSession(
    sessionId: string,
    operationalProcessing: boolean,
    modelTraining: boolean,
  ): Promise<BodyPhotoSession>;
  uploadPhoto(
    sessionId: string,
    view: BodyPhotoView,
    asset: BodyPhotoCapturedAsset,
  ): Promise<BodyPhotoSession>;
}

const basePath = "/api/v1/body-photo-sessions";

export function createBodyPhotoApi(
  request: AuthenticatedBodyPhotoRequest,
  upload?: AuthenticatedBodyPhotoUpload,
  download?: AuthenticatedBodyPhotoDownload,
): BodyPhotoApi {
  return {
    createSession: (purpose) => request<BodyPhotoSession>({
      body: { purpose },
      method: "POST",
      path: basePath,
    }),
    deleteSession: (sessionId) => request<void>({
      method: "DELETE",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}`,
    }),
    downloadPhoto: (sessionId, view) => {
      if (download === undefined) {
        return Promise.reject(new Error("Body-photo downloads are not configured"));
      }
      return download({
        headers: { "Cache-Control": "no-store", Pragma: "no-cache" },
        method: "GET",
        path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/photos/${view}/content`,
        responseType: "binary",
      });
    },
    getAnalysis: (sessionId) => request<BodyAnalysis | null>({
      method: "GET",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/analysis`,
    }),
    getComparison: (sessionId) => request<BodyProgressComparison | null>({
      method: "GET",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/comparison`,
    }),
    getSession: (sessionId) => {
      let normalizedId: string;
      try {
        normalizedId = requireSessionId(sessionId);
      } catch (error) {
        return Promise.reject(error);
      }
      return request<BodyPhotoSession>({
        method: "GET",
        path: `${basePath}/${encodeURIComponent(normalizedId)}`,
      });
    },
    getTimeline: () => request<BodyProgressTimelineResponse>({
      method: "GET",
      path: "/api/v1/body-progress/timeline",
    }),
    listSessions: () => request<BodyPhotoSessionList>({
      method: "GET",
      path: basePath,
    }),
    retryAnalysis: (sessionId, confirmMeasurementsCurrent = true) => request<BodyAnalysis>({
      body: { confirm_measurements_current: confirmMeasurementsCurrent },
      method: "POST",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/analysis/retry`,
    }),
    startAnalysis: (sessionId, confirmMeasurementsCurrent = true) => request<BodyAnalysis>({
      body: { confirm_measurements_current: confirmMeasurementsCurrent },
      method: "POST",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/analysis`,
    }),
    submitSession: (sessionId, operationalProcessing, modelTraining) => request<BodyPhotoSession>({
      body: {
        model_training: {
          granted: modelTraining,
          version: "body-photo-model-training-v1",
        },
        operational_processing: {
          granted: operationalProcessing,
          version: "body-photo-processing-v1",
        },
      },
      method: "POST",
      path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/submit`,
    }),
    uploadPhoto: async (sessionId, view, asset) => {
      if (upload === undefined) {
        throw new Error("Body-photo uploads are not configured");
      }
      if (asset.privacyCropApplied !== true) {
        throw new Error("A body photo must be privacy-cropped before upload");
      }
      const file = new File(asset.uri);
      if (!file.exists) {
        throw new Error("The privacy-cropped body photo is unavailable");
      }
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.byteLength === 0) {
        throw new Error("The privacy-cropped body photo is empty");
      }
      return upload<BodyPhotoSession>({
        method: "PUT",
        parts: [{
          bytes,
          contentType: "image/jpeg",
          filename: `body-${view}.jpg`,
          name: "file",
        }],
        path: `${basePath}/${encodeURIComponent(requireSessionId(sessionId))}/photos/${view}`,
      });
    },
  };
}

function requireSessionId(sessionId: string): string {
  const normalizedId = sessionId.trim();
  if (normalizedId.length === 0) {
    throw new Error("A body-photo session id is required");
  }
  return normalizedId;
}
