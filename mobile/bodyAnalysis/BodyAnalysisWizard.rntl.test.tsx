import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

import type { BodyAnalysis, BodyPhotoView } from "@fitician/core/body-photos";

jest.mock("expo-file-system", () => ({ File: class {} }));
jest.mock("expo-secure-store", () => ({
  deleteItemAsync: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
  getItemAsync: jest.fn<() => Promise<null>>().mockResolvedValue(null),
  setItemAsync: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./BodyPhotoCapture", () => {
  const { Button } = jest.requireActual("../ui/components") as typeof import("../ui/components");
  return {
    BodyPhotoCapture: ({
      onCaptured,
      view,
    }: {
      readonly onCaptured: (asset: {
        readonly height: number;
        readonly mimeType: "image/jpeg";
        readonly privacyCropApplied: true;
        readonly source: "library";
        readonly uri: string;
        readonly width: number;
      }) => void | Promise<void>;
      readonly view: BodyPhotoView;
    }) => (
      <Button
        label={`تأیید ${view}`}
        onPress={() => void onCaptured({
          height: 1920,
          mimeType: "image/jpeg",
          privacyCropApplied: true,
          source: "library",
          uri: `file:///encoded-${view}.jpg`,
          width: 1280,
        })}
      />
    ),
    PhotoClothingGuide: () => null,
  };
});
jest.mock("./bodyPhotoApi", () => ({ createBodyPhotoApi: jest.fn() }));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createProfileApi } from "../profile/profileApi";
import { bodyPhotoCopy } from "./bodyAnalysisCopy";
import { BodyAnalysisWizard } from "./BodyAnalysisWizard";
import { createBodyPhotoApi } from "./bodyPhotoApi";

const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockCreateBodyPhotoApi = jest.mocked(createBodyPhotoApi);

const profile = {
  current_weight_kg: 76.5,
  height_cm: 178,
  hip_circumference_cm: 99,
  shoulder_circumference_cm: 112,
  waist_circumference_cm: 82.5,
};

const createdSession = {
  created_at: "2026-09-09T08:00:00Z",
  id: "body-session-1",
  model_training_consent: null,
  operational_processing_consent: null,
  photos: [],
  purpose: "initial_plan",
  state: "draft",
  submitted_at: null,
  updated_at: "2026-09-09T08:00:00Z",
};

type CreateSession = (purpose: string) => Promise<typeof createdSession>;
type UploadPhoto = (
  sessionId: string,
  view: BodyPhotoView,
  asset: {
    readonly height: number;
    readonly mimeType: "image/jpeg";
    readonly privacyCropApplied: true;
    readonly source: "library";
    readonly uri: string;
    readonly width: number;
  },
) => Promise<typeof createdSession>;

let createSession: jest.Mock<CreateSession>;
let uploadPhoto: jest.Mock<UploadPhoto>;

function renderWizard(onViewAnalysis?: (sessionId: string) => void) {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <BodyAnalysisWizard onExit={jest.fn()} onViewAnalysis={onViewAnalysis} />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  createSession = jest.fn<CreateSession>().mockResolvedValue(createdSession);
  uploadPhoto = jest.fn<UploadPhoto>().mockResolvedValue(createdSession);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
    user: { id: "user-1" },
  } as never);
  mockCreateBodyPhotoApi.mockReturnValue({ createSession, uploadPhoto } as never);
  mockCreateProfileApi.mockReturnValue({
    getProfile: jest.fn<() => Promise<typeof profile>>().mockResolvedValue(profile),
  } as never);
});

test("requires current measurements before starting a secure body-analysis session", async () => {
  renderWizard();

  expect(await screen.findByRole("header", { name: "اندازه‌های فعلی‌ات را تأیید کن" })).toBeTruthy();
  expect(screen.getByText("اندازه‌های پایه")).toBeTruthy();
  expect(screen.getByText("تناسبات بدن")).toBeTruthy();

  const continueButton = await screen.findByLabelText("ذخیره و ادامه");
  expect(continueButton.props.accessibilityState.disabled).toBe(true);

  fireEvent(screen.getByLabelText("تأیید می‌کنم این اندازه‌ها برای همین جلسه عکس فعلی هستند"), "valueChange", true);
  expect(screen.getByLabelText("ذخیره و ادامه").props.accessibilityState.disabled).toBe(false);

  fireEvent.press(screen.getByLabelText("ذخیره و ادامه"));

  await waitFor(() => expect(createSession).toHaveBeenCalledWith("initial_plan"));
});

test("uploads each confirmed view before advancing to the next web view", async () => {
  const uploadedViews: BodyPhotoView[] = [];
  uploadPhoto.mockImplementation(async (_sessionId, view) => {
    uploadedViews.push(view);
    return {
      ...createdSession,
      photos: uploadedViews.map((uploadedView) => ({ view: uploadedView })),
    } as typeof createdSession;
  });

  renderWizard();
  fireEvent(await screen.findByLabelText("تأیید می‌کنم این اندازه‌ها برای همین جلسه عکس فعلی هستند"), "valueChange", true);
  fireEvent.press(await screen.findByLabelText("ذخیره و ادامه"));

  fireEvent.press(await screen.findByLabelText("تأیید front"));
  await waitFor(() => expect(uploadPhoto).toHaveBeenCalledWith(
    "body-session-1",
    "front",
    expect.objectContaining({ uri: "file:///encoded-front.jpg" }),
  ));
  expect(await screen.findByLabelText("تأیید side")).toBeTruthy();

  fireEvent.press(screen.getByLabelText("تأیید side"));
  await waitFor(() => expect(uploadedViews).toEqual(["front", "side"]));
  expect(await screen.findByLabelText("تأیید back")).toBeTruthy();

  fireEvent.press(screen.getByLabelText("تأیید back"));
  await waitFor(() => expect(uploadedViews).toEqual(["front", "side", "back"]));
  expect(await screen.findByText(bodyPhotoCopy.reviewTitle)).toBeTruthy();
  expect(screen.getByText(bodyPhotoCopy.processingTerms)).toBeTruthy();
  expect(screen.getByText(bodyPhotoCopy.modelTraining)).toBeTruthy();
  expect(screen.getByText(bodyPhotoCopy.modelTrainingHint)).toBeTruthy();
  expect(screen.getByLabelText(bodyPhotoCopy.submit)).toBeTruthy();
});

test("shows the web queued state and opens the submitted session result", async () => {
  const uploadedViews: BodyPhotoView[] = [];
  const onViewAnalysis = jest.fn();
  uploadPhoto.mockImplementation(async (_sessionId, view) => {
    uploadedViews.push(view);
    return {
      ...createdSession,
      photos: uploadedViews.map((uploadedView) => ({ view: uploadedView })),
    } as typeof createdSession;
  });
  mockCreateBodyPhotoApi.mockReturnValue({
    createSession,
    startAnalysis: jest.fn<() => Promise<BodyAnalysis>>().mockResolvedValue({
      id: "analysis-1",
      session_id: createdSession.id,
      status: "review_pending",
    } as BodyAnalysis),
    submitSession: jest.fn<() => Promise<typeof createdSession>>().mockResolvedValue({
      ...createdSession,
      photos: ["front", "side", "back"].map((view) => ({ view })),
      state: "queued",
      submitted_at: "2026-09-09T08:05:00Z",
    } as unknown as typeof createdSession),
    uploadPhoto,
  } as never);

  renderWizard(onViewAnalysis);
  fireEvent(await screen.findByLabelText("تأیید می‌کنم این اندازه‌ها برای همین جلسه عکس فعلی هستند"), "valueChange", true);
  fireEvent.press(await screen.findByLabelText("ذخیره و ادامه"));
  fireEvent.press(await screen.findByLabelText("تأیید front"));
  await waitFor(() => expect(uploadedViews).toEqual(["front"]));
  fireEvent.press(await screen.findByLabelText("تأیید side"));
  await waitFor(() => expect(uploadedViews).toEqual(["front", "side"]));
  fireEvent.press(await screen.findByLabelText("تأیید back"));
  await waitFor(() => expect(uploadedViews).toEqual(["front", "side", "back"]));
  expect(await screen.findByText(bodyPhotoCopy.reviewTitle)).toBeTruthy();

  fireEvent(
    screen.getByLabelText(`${bodyPhotoCopy.processingConsentBefore} ${bodyPhotoCopy.processingTerms}`),
    "valueChange",
    true,
  );
  fireEvent.press(screen.getByLabelText(bodyPhotoCopy.submit));

  expect(await screen.findByText(bodyPhotoCopy.queuedTitle)).toBeTruthy();
  expect(screen.getByText(bodyPhotoCopy.queuedBody)).toBeTruthy();
  fireEvent.press(screen.getByLabelText(bodyPhotoCopy.results.viewAnalysis));
  expect(onViewAnalysis).toHaveBeenCalledWith(createdSession.id);
});
