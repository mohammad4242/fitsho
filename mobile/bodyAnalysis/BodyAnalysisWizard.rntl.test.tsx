import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-file-system", () => ({ File: class {} }));
jest.mock("expo-secure-store", () => ({
  deleteItemAsync: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
  getItemAsync: jest.fn<() => Promise<null>>().mockResolvedValue(null),
  setItemAsync: jest.fn<() => Promise<void>>().mockResolvedValue(undefined),
}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("./BodyPhotoCapture", () => ({ BodyPhotoCapture: () => null }));
jest.mock("./bodyPhotoApi", () => ({ createBodyPhotoApi: jest.fn() }));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createProfileApi } from "../profile/profileApi";
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

let createSession: jest.Mock<CreateSession>;

function renderWizard() {
  return render(
    <SafeAreaProvider initialMetrics={{ frame: { height: 800, width: 400, x: 0, y: 0 }, insets: { bottom: 0, left: 0, right: 0, top: 0 } }}>
      <BodyAnalysisWizard onExit={jest.fn()} />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  createSession = jest.fn<CreateSession>().mockResolvedValue(createdSession);
  mockUseMobileAuth.mockReturnValue({
    download: jest.fn(),
    request: jest.fn(),
    upload: jest.fn(),
    user: { id: "user-1" },
  } as never);
  mockCreateBodyPhotoApi.mockReturnValue({ createSession } as never);
  mockCreateProfileApi.mockReturnValue({
    getProfile: jest.fn<() => Promise<typeof profile>>().mockResolvedValue(profile),
  } as never);
});

test("requires current measurements before starting a secure body-analysis session", async () => {
  renderWizard();

  const continueButton = await screen.findByLabelText("ادامه به ثبت عکس‌ها");
  expect(continueButton.props.accessibilityState.disabled).toBe(true);

  fireEvent(screen.getByLabelText("اندازه‌ها مربوط به امروز هستند"), "valueChange", true);
  expect(screen.getByLabelText("ادامه به ثبت عکس‌ها").props.accessibilityState.disabled).toBe(false);

  fireEvent.press(screen.getByLabelText("ادامه به ثبت عکس‌ها"));

  await waitFor(() => expect(createSession).toHaveBeenCalledWith("initial_plan"));
});
