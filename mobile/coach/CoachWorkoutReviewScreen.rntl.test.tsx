import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn(), useQueryClient: jest.fn() }));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: () => () => undefined,
  },
}));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("../accountDeletion/AccountPrivacyLinks", () => ({ AccountPrivacyLinks: () => null }));
jest.mock("./coachWorkoutReviewApi", () => ({ createCoachWorkoutReviewApi: jest.fn() }));

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createCoachWorkoutReviewApi } from "./coachWorkoutReviewApi";
import { CoachWorkoutReviewScreen } from "./CoachWorkoutReviewScreen";

const mockUseQuery = jest.mocked(useQuery);
const mockUseQueryClient = jest.mocked(useQueryClient);
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateApi = jest.mocked(createCoachWorkoutReviewApi);

const queueItem = {
  id: "review-1",
  member_display_name: "محمد",
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  status: "pending",
};

const detail = {
  ...queueItem,
  status: "claimed",
  draft_revision: 1,
  lease_expires_at: "2026-09-09T10:00:00Z",
  coach_note: null,
  draft: {
    days: [{
      day_number: 1,
      exercises: [{
        order_index: 1,
        exercise_id: "exercise-1",
        prescription_mode: "reps",
        sets: 3,
        reps_min: 8,
        reps_max: 12,
        rir: 2,
        rest_seconds: 90,
        notes_en: null,
        notes_fa: null,
      }],
    }],
  },
  source_plan: { plan_duration_weeks: 4, days: [{}] },
  exercise_options: [
    { id: "exercise-1", name_en: "Bench Press", name_fa: "پرس سینه", prescription_mode: "reps" },
    { id: "exercise-2", name_en: "Push-Up", name_fa: "شنا سوئدی", prescription_mode: "reps" },
  ],
  template_selection: {
    selected_template: "four-day-chest-priority",
    explanation_fa: "این ساختار به‌دلیل اولویت عضلانی صریح انتخاب شد.",
    explanation_en: "This structure was selected because of an explicit muscle priority.",
    score: { priority: 100, body_analysis: 20, goal: 10, sex: 0, fallback: 0, total: 130 },
  },
  coach_quality_metrics: { hard_validation_status: "VALID" },
};

const queryClient = {
  setQueryData: jest.fn(),
};

function queryResult<T>(data: T) {
  return {
    data,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
    refetch: jest.fn<() => Promise<undefined>>().mockResolvedValue(undefined),
  } as never;
}

function renderScreen() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <CoachWorkoutReviewScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockUseRouter.mockReturnValue({ back: jest.fn() } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockUseQueryClient.mockReturnValue(queryClient as never);
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const key = queryKey as readonly unknown[];
    if (key[1] === "detail") {
      return key[2] === "selected" ? queryResult(undefined) : queryResult(detail);
    }
    return queryResult([queueItem]);
  });
  mockCreateApi.mockReturnValue({
    approve: jest.fn<() => Promise<typeof detail>>().mockResolvedValue(detail),
    claim: jest.fn<() => Promise<typeof detail>>().mockResolvedValue(detail),
    get: jest.fn<() => Promise<typeof detail>>().mockResolvedValue(detail),
    getAccess: jest.fn<() => Promise<{ authorized: true }>>().mockResolvedValue({ authorized: true }),
    list: jest.fn<() => Promise<Array<typeof queueItem>>>().mockResolvedValue([queueItem]),
    reject: jest.fn<() => Promise<typeof detail>>().mockResolvedValue(detail),
    renew: jest.fn<() => Promise<typeof detail>>().mockResolvedValue(detail),
    saveDraft: jest.fn<() => Promise<typeof detail>>().mockResolvedValue({ ...detail, draft_revision: 2 }),
  } as never);
});

test("claims a case, edits the exercise selection, and saves the current revision", async () => {
  renderScreen();

  fireEvent.press(await screen.findByRole("button", { name: "شروع بازبینی" }));
  expect(await screen.findByText("علت انتخاب برنامه")).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "انتخاب حرکت" }));
  fireEvent.press(await screen.findByRole("button", { name: "شنا سوئدی" }));
  fireEvent.changeText(screen.getByLabelText("ست"), "4");
  fireEvent.press(screen.getByRole("button", { name: "ذخیرهٔ پیش‌نویس" }));

  await waitFor(() => {
    const api = mockCreateApi.mock.results[0]?.value as { readonly saveDraft: jest.Mock };
    expect(api.saveDraft).toHaveBeenCalledWith(
      "review-1",
      expect.objectContaining({
        expected_revision: 1,
        days: expect.arrayContaining([
          expect.objectContaining({
            exercises: expect.arrayContaining([
              expect.objectContaining({ exercise_id: "exercise-2", sets: 4 }),
            ]),
          }),
        ]),
      }),
    );
  });
});

test("returns from the selected case before leaving the coach route", async () => {
  const routerBack = jest.fn();
  mockUseRouter.mockReturnValue({ back: routerBack } as never);
  renderScreen();

  fireEvent.press(await screen.findByRole("button", { name: "شروع بازبینی" }));
  expect((await screen.findAllByText(/پیش‌نویس مربی/)).length).toBeGreaterThan(0);

  fireEvent.press(screen.getByRole("button", { name: "بازگشت" }));
  expect(screen.queryByText(/پیش‌نویس مربی/)).toBeNull();
  expect(routerBack).not.toHaveBeenCalled();

  fireEvent.press(screen.getByRole("button", { name: "بازگشت" }));
  expect(routerBack).toHaveBeenCalledTimes(1);
});
