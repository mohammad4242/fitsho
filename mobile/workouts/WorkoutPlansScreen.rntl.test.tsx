import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn(),
  useQuery: jest.fn(),
  useQueryClient: jest.fn(),
}));
jest.mock("expo-router", () => ({
  useLocalSearchParams: jest.fn(),
  useRouter: jest.fn(),
}));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));
jest.mock("./workoutApi", () => ({ createWorkoutPlanApi: jest.fn() }));
jest.mock("./workoutPdfStore", () => ({
  ExpoWorkoutPlanPdfStore: jest.fn().mockImplementation(() => ({
    get: jest.fn<() => Promise<null>>().mockResolvedValue(null),
    save: jest.fn(),
  })),
}));

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocalSearchParams, useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createProfileApi } from "../profile/profileApi";
import { createWorkoutPlanApi } from "./workoutApi";
import { WorkoutPlansScreen } from "./WorkoutPlansScreen";

const mockPush = jest.fn();
const mockRequest = jest.fn();
const mockDownload = jest.fn();
const mockUseMutation = jest.mocked(useMutation);
const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseLocalSearchParams = jest.mocked(useLocalSearchParams);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockCreateWorkoutPlanApi = jest.mocked(createWorkoutPlanApi);

function queryResult<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
  } as never;
}

function resolved<T>(value: T) {
  return jest.fn<() => Promise<T>>().mockResolvedValue(value);
}

function renderWorkoutPlans() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <WorkoutPlansScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockRequest.mockClear();
  mockDownload.mockClear();
  mockUseLocalSearchParams.mockReturnValue({} as never);
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
  mockUseMobileAuth.mockReturnValue({
    download: mockDownload,
    request: mockRequest,
    status: "signed_in",
    user: { email: "member@example.com", id: "member-1" },
  } as never);
  mockUseQueryClient.mockReturnValue({ setQueryData: jest.fn() } as never);
  mockCreateProfileApi.mockReturnValue({
    getProfile: resolved({ workout_generation_method: "fitsho_coach" }),
    updateProfile: jest.fn(),
  } as never);
  mockCreateWorkoutPlanApi.mockReturnValue({
    generate: jest.fn(),
    get: jest.fn(),
    getActive: resolved(null),
    getHistory: resolved([]),
  } as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[0] === "profile") return queryResult({ workout_generation_method: "fitsho_coach" });
    if (key[1] === "plans") return queryResult([]);
    return queryResult(null);
  });
  mockUseMutation.mockImplementation(() => ({ isPending: false, mutate: jest.fn() }) as never);
});

test("renders the web-parity workout hierarchy and shared generation control", () => {
  renderWorkoutPlans();

  expect(screen.getByRole("header", { name: "برنامه تمرینی من" })).toBeTruthy();
  expect(screen.getByLabelText("4 هفته")).toBeTruthy();
  expect(screen.getByTestId("segmented-control")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "موتور داخلی" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "هوش مصنوعی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "ساخت برنامه تمرینی" })).toBeTruthy();
});

test("keeps generation choices as native touch actions", () => {
  renderWorkoutPlans();

  fireEvent.press(screen.getByRole("radio", { name: "هوش مصنوعی" }));

  expect(screen.getByRole("radio", { name: "هوش مصنوعی" }).props.accessibilityState).toMatchObject({
    selected: true,
  });
});
