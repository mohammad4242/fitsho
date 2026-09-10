import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { BodyProgressTimelineResponse } from "@fitician/core/body-photos";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./bodyPhotoApi", () => ({ createBodyPhotoApi: jest.fn() }));
jest.mock("./bodyPhotoPrivateMedia", () => ({
  createPrivateBodyPhotoClient: jest.fn(() => null),
  loadPrivateBodyPhotoUris: jest.fn().mockResolvedValue({
    back: "file:///private/back.jpg",
    front: "file:///private/front.jpg",
    side: "file:///private/side.jpg",
  } as never),
}));

import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createBodyPhotoApi } from "./bodyPhotoApi";
import { BodyAnalysisHistoryScreen } from "./BodyAnalysisHistoryScreen";

const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateBodyPhotoApi = jest.mocked(createBodyPhotoApi);

function buildTimeline(): BodyProgressTimelineResponse {
  return {
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
          previous_session_date: "2026-08-20T10:00:00Z",
          current_session_date: "2026-09-07T10:00:00Z",
          interval_days: 18,
          before_photos: [{ view: "front" }],
          after_photos: [{ view: "front" }],
          normalized_result: {
            schema_version: "2.0",
            previous_session_date: "2026-08-20T10:00:00Z",
            current_session_date: "2026-09-07T10:00:00Z",
            interval_days: 18,
            measurement_deltas: [],
            visual_transitions: [{ body_area: "shoulders", state: "improved", change_confidence: 0.9 }],
          },
        },
        review_state: {
          coach: { decision: "approved" },
          doctor: { decision: null },
        },
      },
    ],
  } as unknown as BodyProgressTimelineResponse;
}

const populatedTimeline = buildTimeline();
let timelineResponse: BodyProgressTimelineResponse = populatedTimeline;
let mockDeleteSession: jest.Mock;

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
  timelineResponse = populatedTimeline;
  mockPush.mockClear();
  mockReplace.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush, replace: mockReplace } as never);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
    user: null,
  } as never);
  mockDeleteSession = jest.fn(() => Promise.resolve());
  mockCreateBodyPhotoApi.mockReturnValue({
    deleteSession: mockDeleteSession,
    getTimeline: jest.fn<() => Promise<BodyProgressTimelineResponse>>().mockImplementation(
      async () => timelineResponse,
    ),
  } as never);
});

test("renders the web-parity populated landing hierarchy and timeline", async () => {
  renderHistory();

  expect(await screen.findByText("آنالیز هوشمند ترکیب و فرم بدن")).toBeTruthy();
  expect(screen.getByText("Body Analysis")).toBeTruthy();
  expect(screen.getByText("پایش دقیق روند تغییرات فیزیکی، دورسنجی‌ها و ثبت بصری پیشرفت بدن")).toBeTruthy();
  expect(screen.getByText("اختیاری — برای برنامه تمرینی دقیق‌تر و شخصی‌تر، عکس‌های استاندارد بدن را اضافه کن.")).toBeTruthy();
  expect(screen.getByText("حفظ ۱۰۰٪ حریم خصوصی")).toBeTruthy();
  expect(screen.getByText("راهنمای استاندارد Ghost")).toBeTruthy();
  expect(screen.getByText("دورسنجی و تحلیل روند")).toBeTruthy();
  expect(screen.getByText("جلسه جدید آنالیز بدن")).toBeTruthy();
  expect(screen.getByText("۲ جلسه تحلیل ثبت‌شده")).toBeTruthy();
  expect(screen.getByRole("button", { name: "شروع جلسه عکس" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "نشست‌های ناتمام" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "بدن من در گذر زمان" })).toBeTruthy();
  expect(screen.getByText("آخرین اسکن")).toBeTruthy();
  expect(screen.getByText("وزن ثبت‌شده")).toBeTruthy();
  expect(screen.getByText("دور کمر")).toBeTruthy();
  expect(screen.getByText("دور شانه")).toBeTruthy();
  expect(screen.getByText("دور باسن")).toBeTruthy();
  expect(screen.getByText("مقایسه پیشرفت")).toBeTruthy();
  expect(screen.getByText("قبل و بعد")).toBeTruthy();

  expect(screen.queryByText("تاریخچه و روند پیشرفت")).toBeNull();
  expect(screen.queryByText("آخرین وضعیت تحلیل")).toBeNull();
  expect(screen.queryByText("نتیجه آخرین نشست آماده است")).toBeNull();
});

test("keeps the hero visible while the timeline is loading", async () => {
  let resolveTimeline: (value: BodyProgressTimelineResponse) => void = () => undefined;
  const pendingTimeline = new Promise<BodyProgressTimelineResponse>((resolve) => {
    resolveTimeline = resolve;
  });
  mockCreateBodyPhotoApi.mockReturnValue({
    deleteSession: mockDeleteSession,
    getTimeline: jest.fn(() => pendingTimeline),
  } as never);

  renderHistory();

  expect(await screen.findByText("Body Analysis")).toBeTruthy();
  expect(screen.getAllByRole("progressbar").length).toBeGreaterThan(0);

  resolveTimeline(populatedTimeline);
  expect(await screen.findByText("جلسه جدید آنالیز بدن")).toBeTruthy();
});

test("keeps the hero visible and offers retry after a timeline error", async () => {
  mockCreateBodyPhotoApi.mockReturnValue({
    deleteSession: mockDeleteSession,
    getTimeline: jest.fn(async () => {
      throw new Error("timeline unavailable");
    }),
  } as never);

  renderHistory();

  expect(await screen.findByText("Body Analysis")).toBeTruthy();
  expect(await screen.findByText("تاریخچه تحلیل بدن در دسترس نیست")).toBeTruthy();
  expect(screen.getByRole("button", { name: "تلاش دوباره" })).toBeTruthy();
});

test("preserves start, resume, and result navigation", async () => {
  renderHistory();
  await screen.findByText("جلسه جدید آنالیز بدن");

  fireEvent.press(screen.getByRole("button", { name: "شروع جلسه عکس" }));
  fireEvent.press(screen.getByRole("button", { name: "ادامه نشست" }));
  fireEvent.press(screen.getByRole("button", { name: "مشاهده نتیجه" }));

  expect(mockPush).toHaveBeenNthCalledWith(1, "/member/body-analysis-capture");
  expect(mockPush).toHaveBeenNthCalledWith(2, {
    pathname: "/member/body-analysis-capture",
    params: { sessionId: "incomplete-1" },
  });
  expect(mockPush).toHaveBeenNthCalledWith(3, "/member/body-analysis-result/latest-1");
});

test("uses a dedicated delete dialog and keeps deletion semantics", async () => {
  renderHistory();
  await screen.findByText("جلسه جدید آنالیز بدن");

  fireEvent.press(screen.getByRole("button", { name: "حذف تحلیل" }));
  expect(screen.getByRole("header", { name: "تحلیل ثبت‌شده حذف شود؟" })).toBeTruthy();
  expect(screen.getByText("تکمیل‌شده")).toBeTruthy();
  expect(screen.getByRole("button", { name: "نگه‌داشتن جلسه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "حذف دائمی" })).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "نگه‌داشتن جلسه" }));
  expect(screen.queryByRole("header", { name: "تحلیل ثبت‌شده حذف شود؟" })).toBeNull();

  fireEvent.press(screen.getByRole("button", { name: "حذف تحلیل" }));
  fireEvent.press(screen.getByRole("button", { name: "حذف دائمی" }));
  await waitFor(() => expect(mockDeleteSession).toHaveBeenCalledWith("latest-1"));
});

test("renders the web empty state with scanner visual, steps, and capture CTA", async () => {
  timelineResponse = { schema_version: "1.0", items: [] };
  renderHistory();

  expect(await screen.findByText("هیچ عکسی ثبت نشده است")).toBeTruthy();
  expect(screen.getByText("برای شروع تحلیل، از بدن خود در حالت ایستاده عکس‌های استاندارد بگیر.")).toBeTruthy();
  expect(screen.getByText("عکاسی ۳ زاویه")).toBeTruthy();
  expect(screen.getByText("برش امن چهره")).toBeTruthy();
  expect(screen.getByText("تحلیل و دورسنجی")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ثبت عکس‌های جدید" })).toBeTruthy();
  expect(screen.queryByText("جلسه جدید آنالیز بدن")).toBeNull();
});
