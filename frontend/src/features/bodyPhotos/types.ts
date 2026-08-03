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
  client_crop_confidence: number;
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

export type BodyArea =
  | "shoulders"
  | "chest"
  | "back"
  | "lats"
  | "arms"
  | "forearms"
  | "waist_midsection"
  | "glutes"
  | "quads"
  | "hamstrings"
  | "calves"
  | "symmetry"
  | "visible_alignment_or_posture";

export type BodyAnalysisClassification =
  | "strength"
  | "mild_lag"
  | "clear_lag"
  | "uncertain"
  | "neutral";

export type BodyAnalysisStatus =
  | "queued"
  | "validating"
  | "analyzing"
  | "review_pending"
  | "completed"
  | "failed";

export type PhotoValidationReason =
  | "exactly_one_person_required"
  | "full_body_not_visible"
  | "wrong_view"
  | "low_lighting"
  | "low_sharpness"
  | "clothing_obscures_body"
  | "unsuitable_background"
  | "photo_uncertain";

export type BodyPhotoPreflight = {
  accepted: boolean;
  confidence: number;
  issues: Array<{ view: BodyPhotoView; reasons: PhotoValidationReason[] }>;
};

export type BodyAnalysisFinding = {
  body_area: BodyArea;
  classification: BodyAnalysisClassification;
  severity: number | null;
  confidence: number;
  supporting_views: BodyPhotoView[];
  explanation: string;
  limitations: string[];
  suggested_training_emphasis: string[];
  medical_review_recommended: boolean;
};

export type NormalizedBodyAnalysis = {
  schema_version: string;
  overall_confidence: number;
  findings: BodyAnalysisFinding[];
  summary: {
    visible_strengths: BodyArea[];
    priority_areas: BodyArea[];
    moderate_attention_areas: BodyArea[];
    uncertain_areas: BodyArea[];
  };
  requires_coach_review: true;
  requires_doctor_review: true;
};

export type SpecialistReviewState = {
  role: "coach" | "doctor";
  decision: "approved" | "changes_required" | "rejected" | null;
  reviewed_at: string | null;
  reviewed_result_version: number | null;
};

export type BodyAnalysis = {
  id: string;
  session_id: string;
  revision: number;
  status: BodyAnalysisStatus;
  provider: string;
  model_id: string;
  schema_version: string;
  result_version: number | null;
  result_source: "ai" | "coach" | "doctor" | null;
  normalized_result: NormalizedBodyAnalysis | null;
  overall_confidence: number | null;
  coach_review: SpecialistReviewState;
  doctor_review: SpecialistReviewState;
  fully_reviewed: boolean;
  unverified_warning: boolean;
  safe_error_message: string | null;
  photo_validation: BodyPhotoPreflight | null;
  created_at: string;
  completed_at: string | null;
};

export type BodyProgressState =
  | "improved"
  | "unchanged"
  | "declined_or_less_balanced"
  | "uncertain";

export type BodyAreaComparison = {
  bodyArea: BodyArea;
  state: BodyProgressState;
  previousClassification: BodyAnalysisClassification | null;
  currentClassification: BodyAnalysisClassification | null;
  confidence: number;
};
