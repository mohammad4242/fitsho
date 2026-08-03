import { request } from "../../shared/apiClient";

import type { BodyPhotoPurpose, BodyPhotoSession, BodyPhotoSessionList, BodyPhotoView } from "./types";
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
    headers: {
      "X-Fitsho-Client-Crop-Confirmed": "true",
      "X-Fitsho-Crop-Confidence": String(processed.cropConfidence),
      "X-Fitsho-Original-Height": String(processed.originalHeight),
      "X-Fitsho-Crop-Top": String(processed.cropTop),
      "X-Fitsho-Crop-Bottom": String(processed.cropBottom),
      "X-Fitsho-Processed-SHA256": processed.processedSha256,
      "X-Fitsho-Crop-Evidence-SHA256": processed.cropEvidenceSha256,
    },
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
