export type BodyPhotoView = "front" | "side" | "back";
export type BodyPhotoPurpose = "initial_plan" | "cycle_completion" | "progress_check";
export type BodyPhotoSessionState =
  | "draft"
  | "awaiting_consent"
  | "uploading"
  | "uploaded"
  | "queued"
  | "validating"
  | "analyzing"
  | "review_pending"
  | "completed"
  | "failed"
  | "deleted";

export type BodyPhoto = {
  id: string;
  view: BodyPhotoView;
  mime_type: string;
  byte_size: number;
  width: number;
  height: number;
  crop_confidence: number;
  client_crop_confirmed: boolean;
  server_geometry_checked: boolean;
  content_url: string;
  created_at: string;
  updated_at: string;
};

export type BodyPhotoConsent = {
  granted: boolean;
  version: string;
  recorded_at: string;
};

export type BodyPhotoSession = {
  id: string;
  purpose: BodyPhotoPurpose;
  state: BodyPhotoSessionState;
  photos: BodyPhoto[];
  operational_processing_consent: BodyPhotoConsent | null;
  model_training_consent: BodyPhotoConsent | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BodyPhotoSessionList = { items: BodyPhotoSession[] };
