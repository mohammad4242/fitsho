import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type {
  BodyAnalysis,
  BodyAnalysisExperienceV4,
  BodyPhotoSession,
  BodyProgressComparison,
} from "@fitician/core/body-photos";

jest.mock("expo-router", () => ({ useLocalSearchParams: jest.fn(), useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../media/privateMedia", () => ({
  PrivateMediaClient: jest.fn().mockImplementation(() => ({ download: jest.fn() })),
}));
jest.mock("../media/privateMediaStore", () => ({ ExpoPrivateMediaStore: jest.fn() }));
jest.mock("./bodyPhotoApi", () => ({ createBodyPhotoApi: jest.fn() }));

import { useLocalSearchParams, useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyAnalysisResultScreen } from "./BodyAnalysisResultScreen";

const mockUseLocalSearchParams = jest.mocked(useLocalSearchParams);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateBodyPhotoApi = jest.mocked(createBodyPhotoApi);
const mockReplace = jest.fn();

const experience = {
  schema_version: "4.0",
  presentation_version: "body-analysis-experience-v2",
  assessment_status: "complete",
  input_snapshot: {
    captured_at: "2026-09-08T10:00:00Z",
    confirmed_at: "2026-09-08T10:00:00Z",
    profile_updated_at: "2026-09-08T09:00:00Z",
    measurement_id: "measurement-1",
    measurement_measured_at: "2026-09-08T09:00:00Z",
    sex: "male",
    height_cm: 178,
    weight_kg: 82.5,
    shoulder_circumference_cm: 122,
    waist_circumference_cm: 84,
    hip_circumference_cm: 98,
    selected_goal: "build_muscle",
  },
  body_composition: {
    bmi: 26,
    estimated_body_fat_percent: 21.6,
    body_fat_estimation_method: "rfm",
    body_fat_is_estimate: true,
  },
  first_impression: {
    message_key: "body_analysis.first_impression.primary_priority",
    parameters: { areas: ["shoulders"] },
  },
  direction: {
    status: "aligned_with_current_goal",
    goal: "build_muscle",
    reason_codes: ["current_goal_preserved"],
  },
  indicators: {
    upper_lower_balance: { status: "balanced", score_percent: 90 },
    visible_symmetry: { status: "no_clear_difference", score_percent: 91 },
    muscle_balance: { status: "available", score_percent: 85 },
    body_shape: { status: "available", score_percent: 82 },
  },
  regions: [
    {
      area: "shoulders",
      display_classification: "primary_priority",
      insight_key: "body_analysis.insights.primary_priority",
      insight_parameters: { area: "shoulders" },
      supporting_views: ["front", "back"],
    },
    {
      area: "arms",
      display_classification: "stronger",
      insight_key: "body_analysis.insights.stronger",
      insight_parameters: { area: "arms" },
      supporting_views: ["front"],
    },
  ],
  review_notice_code: "review_pending",
} as unknown as BodyAnalysisExperienceV4;

const session = {
  id: "session-1",
  purpose: "progress_check",
  state: "review_pending",
  photos: [],
  operational_processing_consent: null,
  model_training_consent: null,
  submitted_at: "2026-09-08T10:00:00Z",
  created_at: "2026-09-08T10:00:00Z",
  updated_at: "2026-09-08T10:00:00Z",
} as unknown as BodyPhotoSession;

const analysis = {
  id: "analysis-1",
  session_id: "session-1",
  revision: 1,
  status: "review_pending",
  provider: "openrouter",
  model_id: "vision-model",
  schema_version: "4.0",
  result_version: 2,
  result_source: "ai",
  normalized_result: null,
  experience_result: experience,
  overall_confidence: 0.84,
  coach_review: { role: "coach", decision: null, reviewed_at: null, reviewed_result_version: null },
  doctor_review: { role: "doctor", decision: "approved", reviewed_at: "2026-09-08T12:00:00Z", reviewed_result_version: 2 },
  fully_reviewed: false,
  unverified_warning: true,
  error_code: null,
  safe_error_message: null,
  photo_validation: null,
  created_at: "2026-09-08T10:00:00Z",
  completed_at: "2026-09-08T10:01:00Z",
} as unknown as BodyAnalysis;

const comparison = {
  normalized_result: {
    schema_version: "2.0",
    previous_session_date: "2026-08-11T10:00:00Z",
    current_session_date: "2026-09-08T10:00:00Z",
    interval_days: 28,
    measurement_deltas: [
      { measurement: "weight_kg", availability: "exact", previous: 84, current: 82.5, unit: "kg" },
    ],
    visual_transitions: [{ body_area: "shoulders", state: "improved", change_confidence: 0.8 }],
  },
} as unknown as BodyProgressComparison;

function renderResult() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <BodyAnalysisResultScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockUseLocalSearchParams.mockReturnValue({ sessionId: "session-1" });
  mockUseRouter.mockReturnValue({ replace: mockReplace } as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
    user: { id: "user-1" },
  } as never);
  mockCreateBodyPhotoApi.mockReturnValue({
    getSession: jest.fn<() => Promise<BodyPhotoSession>>().mockResolvedValue(session),
    getAnalysis: jest.fn<() => Promise<BodyAnalysis | null>>().mockResolvedValue(analysis),
    getComparison: jest.fn<() => Promise<BodyProgressComparison | null>>().mockResolvedValue(comparison),
  } as never);
  mockReplace.mockClear();
});

test("follows the Web result story with real metrics, findings, reviews, and comparison", async () => {
  renderResult();

  expect(await screen.findByRole("header", { name: "تحلیل بدن" })).toBeTruthy();
  expect(screen.getByText("درصد چربی تخمینی")).toBeTruthy();
  expect(screen.getByText("شاخص‌های بصری بدن")).toBeTruthy();
  expect(screen.getByRole("header", { name: "یافته‌های همین تحلیل" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "سرشانه" })).toBeTruthy();
  expect(screen.getAllByText("بازوها").length).toBeGreaterThan(0);
  expect(screen.getByRole("header", { name: "بازبینی متخصصان" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "مقایسه پیشرفت" })).toBeTruthy();
  expect(screen.queryByText("نسخه نتیجه")).toBeNull();

  fireEvent.press(screen.getByRole("button", { name: "سرشانه" }));
  expect(screen.getByText(/نسبت به بقیه بدنت عقب‌تره/)).toBeTruthy();

  expect(screen.getByText(/این بررسی توسط AI انجام شده/)).toBeTruthy();
});
