import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { BodyProgressTimelineResponse } from "@fitician/core/body-photos";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./bodyPhotoApi", () => ({ createBodyPhotoApi: jest.fn() }));

import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyAnalysisHistoryScreen } from "./BodyAnalysisHistoryScreen";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateBodyPhotoApi = jest.mocked(createBodyPhotoApi);

const timeline = {
  schema_version: "1.0",
  items: [
    {
      session: {
        id: "incomplete-1",
        cycle_id: null,
        purpose: "progress_check",
        state: "uploading",
        submitted_at: null,
        created_at: "2026-09-08T10:00:00Z",
        updated_at: "2026-09-08T10:00:00Z",
      },
      photos: [{ view: "front" }],
      analysis: null,
      snapshot: null,
      comparison: null,
      review_state: {
        coach: { decision: null },
        doctor: { decision: null },
      },
    },
    {
      session: {
        id: "latest-1",
        cycle_id: null,
        purpose: "initial_plan",
        state: "completed",
        submitted_at: "2026-09-07T10:00:00Z",
        created_at: "2026-09-07T10:00:00Z",
        updated_at: "2026-09-07T10:00:00Z",
      },
      photos: [{ view: "front" }, { view: "side" }, { view: "back" }],
      analysis: { result_version: 2 },
      snapshot: {
        weight_kg: 76.5,
        waist_circumference_cm: 82,
        shoulder_circumference_cm: 112,
        hip_circumference_cm: 99,
      },
      comparison: {
        normalized_result: {
          schema_version: "2.0",
          visual_transitions: [{ state: "improved" }],
        },
      },
      review_state: {
        coach: { decision: "approved" },
        doctor: { decision: null },
      },
    },
  ],
} as unknown as BodyProgressTimelineResponse;

function renderHistory() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <BodyAnalysisHistoryScreen tabRoot />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockReplace.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush, replace: mockReplace } as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
  } as never);
  mockCreateBodyPhotoApi.mockReturnValue({
    deleteSession: jest.fn(),
    getTimeline: jest.fn<() => Promise<BodyProgressTimelineResponse>>().mockResolvedValue(timeline),
  } as never);
});

test("shows latest progress context while keeping capture and resume explicit", async () => {
  renderHistory();

  expect(await screen.findByRole("header", { name: "تاریخچه و روند پیشرفت" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "آخرین وضعیت تحلیل" })).toBeTruthy();
  expect(screen.getByText("نتیجه آخرین نشست آماده است")).toBeTruthy();
  expect(screen.getByText("وزن ثبت‌شده")).toBeTruthy();
  expect(screen.getAllByText("۱ تغییر بصری با مقایسه استاندارد ثبت شده است.")).toHaveLength(2);
  expect(screen.getByRole("header", { name: "نشست‌های ناتمام" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "روند تحلیل‌ها" })).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "تحلیل جدید" }));
  fireEvent.press(screen.getByRole("button", { name: "ادامه نشست" }));
  fireEvent.press(screen.getByRole("button", { name: "مشاهده آخرین نتیجه" }));

  expect(mockPush).toHaveBeenNthCalledWith(1, "/member/body-analysis");
  expect(mockPush).toHaveBeenNthCalledWith(2, {
    pathname: "/member/body-analysis",
    params: { sessionId: "incomplete-1" },
  });
  expect(mockPush).toHaveBeenNthCalledWith(3, "/member/body-analysis-result/latest-1");
});
