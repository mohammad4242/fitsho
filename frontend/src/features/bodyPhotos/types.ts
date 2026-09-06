export type BodyPhotoView = "front" | "side" | "back";
export type BodyPhotoSide = "right" | "left";

export type GhostTransform = {
  scale: number;
  translateX: number;
  translateY: number;
  rotation: number;
};
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

export type BodyAnalysisExperienceSex = "female" | "male" | "other" | "prefer_not_to_say";
export type BodyAnalysisExperienceGoal =
  | "lose_weight"
  | "gain_weight"
  | "fat_loss"
  | "build_muscle"
  | "body_recomposition"
  | "strength"
  | "improve_fitness"
  | "maintain_weight";

export type BodyAnalysisExperienceMessage = {
  message_key: string;
  parameters: Record<string, unknown>;
};

export type BodyAnalysisExperienceDirection = {
  status: "aligned_with_current_goal" | "goal_confirmation_required";
  goal: BodyAnalysisExperienceGoal | null;
  reason_codes: string[];
};

export type BodyAnalysisInputSnapshot = {
  captured_at: string;
  confirmed_at: string;
  profile_updated_at: string;
  measurement_id: string;
  measurement_measured_at: string;
  sex: BodyAnalysisExperienceSex;
  height_cm: number;
  weight_kg: number;
  shoulder_circumference_cm: number;
  waist_circumference_cm: number;
  hip_circumference_cm: number;
  selected_goal: BodyAnalysisExperienceGoal;
};

export type BodyAnalysisExperienceIndicator = {
  status: string;
  message_key: string;
  parameters: Record<string, unknown>;
  score_percent: number | null;
};

export type BodyAnalysisExperienceIndicators = {
  upper_lower_balance: BodyAnalysisExperienceIndicator;
  visible_symmetry: BodyAnalysisExperienceIndicator;
  muscle_balance: BodyAnalysisExperienceIndicator;
  body_shape: BodyAnalysisExperienceIndicator;
};

export type BodyCompositionMetrics = {
  bmi: number | null;
  estimated_body_fat_percent: number | null;
  body_fat_estimation_method: "rfm" | null;
  body_fat_is_estimate: boolean;
};

export type BodyAnalysisExperienceRegion = {
  area: Exclude<BodyArea, "symmetry" | "visible_alignment_or_posture">;
  display_classification: "stronger" | "balanced" | "room_to_grow" | "primary_priority" | "not_assessable";
  insight_key: string | null;
  insight_parameters: Record<string, unknown>;
  supporting_views: BodyPhotoView[];
};

export type BodyAnalysisExperienceV4 = {
  schema_version: "4.0";
  presentation_version: "body-analysis-experience-v2";
  assessment_status: VisualAssessmentStatus;
  input_snapshot: BodyAnalysisInputSnapshot;
  body_composition: BodyCompositionMetrics;
  first_impression: BodyAnalysisExperienceMessage;
  direction: BodyAnalysisExperienceDirection;
  indicators: BodyAnalysisExperienceIndicators;
  regions: BodyAnalysisExperienceRegion[];
  review_notice_code: string;
};

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

export type VisualAssessmentStatus = "complete" | "partial";

export type VisualPhysiqueFinding = {
  area: BodyArea;
  classification: BodyAnalysisClassification | "not_assessable";
  severity: number | null;
  confidence: number;
  views_used: BodyPhotoView[];
  evidence_fa: string;
  suggested_training_emphasis: string[];
};

export type VisualPhysiqueAssessment = {
  assessment_status: VisualAssessmentStatus;
  photo_quality: {
    front: { usable: boolean; issues_fa: string[] };
    side: { usable: boolean; issues_fa: string[] };
    back: { usable: boolean; issues_fa: string[] };
    global_limitations_fa: string[];
  };
  overall_assessment: {
    development_pattern: string;
    shoulder_to_waist_taper: string;
    upper_lower_balance: string;
    summary_fa: string;
  };
  findings: VisualPhysiqueFinding[];
  medical_review_recommended: false;
  human_coach_review_required: true;
  human_doctor_review_required: true;
  provisional_notice_fa: string;
};

export type VisualChecklistRating =
  | "excellent"
  | "good"
  | "average"
  | "needs_attention"
  | "focus_priority"
  | "not_assessable";

export type VisualPhysiqueAssessmentV3 = Omit<VisualPhysiqueAssessment, "findings"> & {
  goal_suggestion: {
    suggested_goal: "lose_weight" | "maintain_weight" | "build_muscle" | "gain_weight";
    reasoning_fa: string;
    inputs_unavailable_fa: string[];
  };
  findings: Array<{
    area: BodyArea;
    front: { rating: VisualChecklistRating; evidence_fa: string };
    side: { rating: VisualChecklistRating; evidence_fa: string };
    back: { rating: VisualChecklistRating; evidence_fa: string };
    overall_rating: VisualChecklistRating;
    overall_summary_fa: string;
    confidence: number;
    suggested_training_emphasis: string[];
  }>;
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
  visual_result?: VisualPhysiqueAssessment | VisualPhysiqueAssessmentV3 | null;
  experience_result?: BodyAnalysisExperienceV4 | null;
  overall_confidence: number | null;
  coach_review: SpecialistReviewState;
  doctor_review: SpecialistReviewState;
  fully_reviewed: boolean;
  unverified_warning: boolean;
  error_code: string | null;
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

export type BodyProgressProvenanceSource =
  | "body_analysis_input_snapshot"
  | "cycle_measurement"
  | "normalized_result"
  | "unavailable";

export type BodyProgressProvenanceReasonCode =
  | "exact_analysis_input_snapshot"
  | "exact_cycle_measurement"
  | "measurement_unavailable_for_legacy_scan"
  | "effective_normalized_result";

export type BodyProgressVisualReasonCode =
  | "classification_changed"
  | "classification_unchanged"
  | "missing_previous_observation"
  | "missing_current_observation"
  | "incomplete_standardized_views"
  | "no_common_supporting_view"
  | "low_confidence"
  | "specialist_corrected_result";

export type BodyProgressProvenance = {
  source: BodyProgressProvenanceSource;
  reference_id: string | null;
  recorded_at: string | null;
  reason_code: BodyProgressProvenanceReasonCode;
};

export type BodyProgressItemProvenance = {
  previous: BodyProgressProvenance;
  current: BodyProgressProvenance;
};

export type BodyProgressMeasurementName =
  | "weight_kg"
  | "shoulder_circumference_cm"
  | "waist_circumference_cm"
  | "hip_circumference_cm";

export type BodyProgressMeasurementDelta = {
  measurement: BodyProgressMeasurementName;
  unit: "kg" | "cm";
  previous: number | null;
  current: number | null;
  delta: number | null;
  availability: "exact" | "unavailable";
  provenance: BodyProgressItemProvenance;
};

export type BodyProgressVisualTransition = {
  body_area: BodyArea;
  state: BodyProgressState;
  previous_classification: BodyAnalysisClassification | null;
  current_classification: BodyAnalysisClassification | null;
  change_confidence: number;
  supporting_views: readonly BodyPhotoView[];
  reason_codes: readonly BodyProgressVisualReasonCode[];
  provenance: BodyProgressItemProvenance;
};

export type BodyProgressPersistentPriority = {
  body_area: BodyArea;
  provenance: BodyProgressItemProvenance;
};

export type NormalizedBodyProgressComparisonV1 = {
  schema_version: "1.0";
  overall_confidence: number;
  previous_session_id: string;
  current_session_id: string;
  previous_result_version_id: string;
  current_result_version_id: string;
  areas: Array<{
    body_area: BodyArea;
    state: BodyProgressState;
    previous_classification: BodyAnalysisClassification | null;
    current_classification: BodyAnalysisClassification | null;
    change_confidence: number;
    supporting_views: BodyPhotoView[];
    explanation: string;
    limitations: string[];
  }>;
  summary: string;
};

export type NormalizedBodyProgressComparisonV2 = {
  schema_version: "2.0";
  overall_confidence: number;
  previous_session_id: string;
  current_session_id: string;
  previous_result_version_id: string;
  current_result_version_id: string;
  previous_session_date: string;
  current_session_date: string;
  interval_days: number;
  measurement_deltas: BodyProgressMeasurementDelta[];
  visual_transitions: BodyProgressVisualTransition[];
  persistent_priorities: BodyProgressPersistentPriority[];
  measurement_notice_code: "measurements_recorded_by_user";
  visual_observation_notice_code: "standardized_photo_observation_not_direct_measurement";
};

export type BodyProgressComparisonQuality = {
  analysis_confidence: number;
  all_standardized_views_present: boolean;
};

export type BodyProgressComparisonContext = {
  previous_feedback_id?: string | null;
  current_feedback_id?: string | null;
  previous_adherence_percent?: number | null;
  current_adherence_percent?: number | null;
  previous_performance_feedback_available?: boolean;
  current_performance_feedback_available?: boolean;
  current_pain_or_limitation_feedback_available?: boolean;
  user_reported_measurement_changes: Record<string, {
    previous: number;
    current: number;
    delta: number;
  }>;
};

export type BodyProgressComparison = {
  id: string;
  previous_session_id: string;
  current_session_id: string;
  previous_result_version_id: string;
  current_result_version_id: string;
  comparison_version: number;
  schema_version: "1.0" | "2.0";
  normalized_result: NormalizedBodyProgressComparisonV1 | NormalizedBodyProgressComparisonV2;
  quality_snapshot: Record<string, BodyProgressComparisonQuality>;
  context_snapshot: BodyProgressComparisonContext;
  created_at: string;
};

export type BodyProgressTimelineComparison = BodyProgressComparison & {
  previous_session_date: string;
  current_session_date: string;
  interval_days: number;
  before_photos: BodyPhoto[];
  after_photos: BodyPhoto[];
};

export type BodyProgressTimelineSession = {
  id: string;
  cycle_id: string | null;
  purpose: BodyPhotoPurpose;
  state: BodyPhotoSessionState;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type BodyProgressTimelineReviewState = {
  coach: SpecialistReviewState;
  doctor: SpecialistReviewState;
  fully_reviewed: boolean;
};

export type BodyProgressTimelineItem = {
  session: BodyProgressTimelineSession;
  photos: BodyPhoto[];
  analysis: BodyAnalysis | null;
  snapshot: BodyAnalysisInputSnapshot | null;
  comparison: BodyProgressTimelineComparison | null;
  review_state: BodyProgressTimelineReviewState;
};

export type BodyProgressTimelineResponse = {
  schema_version: "1.0";
  items: BodyProgressTimelineItem[];
};
