import { request } from "../../shared/apiClient";

import type {
  BodyAnalysis,
  BodyProgressComparison,
  BodyProgressTimelineResponse,
  BodyPhotoPurpose,
  BodyPhotoSession,
  BodyPhotoSessionList,
  BodyPhotoView,
} from "./types";
import type { ProcessedBodyPhoto } from "./processor";

const basePath = "/api/v1/body-photo-sessions";

export function createBodyPhotoSession(purpose: BodyPhotoPurpose): Promise<BodyPhotoSession> {
  return request<BodyPhotoSession>(basePath, {
    method: "POST",
    body: JSON.stringify({ purpose }),
  });
}

export function getBodyPhotoSessions(): Promise<BodyPhotoSessionList> {
  return request<BodyPhotoSessionList>(basePath);
}

export function getBodyPhotoSession(sessionId: string): Promise<BodyPhotoSession> {
  return request<BodyPhotoSession>(`${basePath}/${sessionId}`);
}

export function uploadBodyPhoto(
  sessionId: string,
  view: BodyPhotoView,
  processed: ProcessedBodyPhoto,
): Promise<BodyPhotoSession> {
  const data = new FormData();
  data.append("file", processed.file, processed.file.name);
  return request<BodyPhotoSession>(`${basePath}/${sessionId}/photos/${view}`, {
    method: "PUT",
    body: data,
  });
}

export function submitBodyPhotoSession(
  sessionId: string,
  operationalProcessing: boolean,
  modelTraining: boolean,
): Promise<BodyPhotoSession> {
  return request<BodyPhotoSession>(`${basePath}/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      operational_processing: { granted: operationalProcessing, version: "body-photo-processing-v1" },
      model_training: { granted: modelTraining, version: "body-photo-model-training-v1" },
    }),
  });
}

export function deleteBodyPhotoSession(sessionId: string): Promise<void> {
  return request<void>(`${basePath}/${sessionId}`, { method: "DELETE" });
}

export function getBodyPhotoAnalysis(sessionId: string): Promise<BodyAnalysis | null> {
  return request<BodyAnalysis | null>(`${basePath}/${sessionId}/analysis`);
}

export function getBodyPhotoComparison(sessionId: string): Promise<BodyProgressComparison | null> {
  return request<BodyProgressComparison | null>(`${basePath}/${sessionId}/comparison`);
}

export function getBodyProgressTimeline(): Promise<BodyProgressTimelineResponse> {
  return request<BodyProgressTimelineResponse>("/api/v1/body-progress/timeline");
}

export function startBodyPhotoAnalysis(
  sessionId: string,
  confirmMeasurementsCurrent = true,
): Promise<BodyAnalysis> {
  return request<BodyAnalysis>(`${basePath}/${sessionId}/analysis`, {
    method: "POST",
    body: JSON.stringify({ confirm_measurements_current: confirmMeasurementsCurrent }),
  });
}

export function retryBodyPhotoAnalysis(sessionId: string): Promise<BodyAnalysis> {
  return request<BodyAnalysis>(`${basePath}/${sessionId}/analysis/retry`, { method: "POST" });
}
