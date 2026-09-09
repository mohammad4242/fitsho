import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

const mockVideoPlayer = {
  addListener: jest.fn(),
  status: "idle",
};
const mockVideoSources: unknown[] = [];

jest.mock("@tanstack/react-query", () => ({ useQuery: jest.fn() }));
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ slug: "incline-press" }),
  useRouter: () => ({ back: jest.fn() }),
}));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../config/nativeRuntimeConfig", () => ({
  getMobileRuntimeConfig: () => ({ apiBaseUrl: "https://api.example.com" }),
}));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("../ui/rtl", () => ({ languageForDirection: jest.fn() }));
jest.mock("expo-video", () => {
  const React = jest.requireActual("react") as typeof import("react");
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    useVideoPlayer: (source: unknown, setup?: (player: typeof mockVideoPlayer) => void) => {
      mockVideoSources.push(source);
      setup?.(mockVideoPlayer);
      return mockVideoPlayer;
    },
    VideoView: (props: Record<string, unknown>) => React.createElement(View, { testID: "native-video", ...props }),
  };
});

import { useQuery } from "@tanstack/react-query";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { languageForDirection } from "../ui/rtl";
import type { ExerciseDetail } from "./exerciseApi";
import { ExerciseDetailScreen } from "./ExerciseDetailScreen";

const mockUseQuery = jest.mocked(useQuery);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockLanguageForDirection = jest.mocked(languageForDirection);

const maleDetail = createDetail([
  asset("male", "/media/male-1.mp4", 0),
  asset("male", "/media/male-2.mp4", 1),
]);
const femaleDetail = createDetail([
  asset("female", "/media/female-1.mp4", 0),
  asset("female", "/media/female-2.mp4", 1),
]);
const inventoryDetail = createDetail([
  asset("male", "/media/male-1.mp4", 0),
  asset("male", "/media/male-2.mp4", 1),
  asset("female", "/media/female-1.mp4", 2),
  asset("female", "/media/female-2.mp4", 3),
]);

beforeEach(() => {
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockLanguageForDirection.mockReturnValue("fa");
  mockVideoSources.length = 0;
  mockVideoPlayer.addListener.mockClear();
  mockUseQuery.mockImplementation(({ queryKey }) => {
    const lastKey = queryKey[queryKey.length - 1];
    const data = lastKey === "media-inventory"
      ? inventoryDetail
      : lastKey === "female"
        ? femaleDetail
        : maleDetail;
    return {
      data,
      error: null,
      isError: false,
      isFetching: false,
      isPending: false,
      isStale: false,
    } as never;
  });
});

function renderDetail() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 400, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <ExerciseDetailScreen />
    </SafeAreaProvider>,
  );
}

test("keeps the exercise card compact, localized, and free of offline or text media controls", () => {
  renderDetail();

  expect(screen.getByTestId("exercise-media-card-title").props.children).toBe("پرس بالا سینه دمبل");
  expect(screen.queryByText("Dumbbell Incline Bench Press")).toBeNull();
  expect(screen.getByText("1/2")).toBeTruthy();
  expect(screen.getByRole("radio", { name: "ویدیوی مرد" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "ویدیوی زن" })).toBeTruthy();
  expect(screen.queryByText("ذخیره برای استفاده آفلاین")).toBeNull();
  expect(screen.queryByText("رسانه نمایش")).toBeNull();
  expect(screen.queryByText("ویدیوی مرد 1")).toBeNull();
});

test("resets the carousel to the first female video after switching gender", () => {
  renderDetail();

  expect(mockVideoSources.at(-1)).toEqual({ uri: "https://api.example.com/media/male-1.mp4" });
  fireEvent.press(screen.getByRole("radio", { name: "ویدیوی زن" }));

  expect(screen.getByText("1/2")).toBeTruthy();
  expect(mockVideoSources.at(-1)).toEqual({ uri: "https://api.example.com/media/female-1.mp4" });
});

test("uses only the English card title and labels when the native direction is LTR", () => {
  mockLanguageForDirection.mockReturnValue("en");
  renderDetail();

  expect(screen.getByTestId("exercise-media-card-title").props.children).toBe("Dumbbell Incline Bench Press");
  expect(screen.getByRole("radio", { name: "Male video" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "Female video" })).toBeTruthy();
});

test("does not switch media from a normal player-control tap", () => {
  renderDetail();

  const surface = screen.getByTestId("exercise-media-surface");
  fireEvent(surface, "responderGrant", { nativeEvent: { locationY: 220 } });
  fireEvent(surface, "responderRelease", { nativeEvent: {}, gestureState: { dx: 4, dy: 1 } });
  expect(mockVideoSources.at(-1)).toEqual({ uri: "https://api.example.com/media/male-1.mp4" });
  expect(screen.getByText("1/2")).toBeTruthy();
});

function asset(
  presentation: "male" | "female",
  mediaPath: string,
  sortOrder: number,
) {
  return {
    media_attribution: null,
    media_path: mediaPath,
    media_type: "video",
    presentation,
    role: "primary",
    sort_order: sortOrder,
  };
}

function createDetail(mediaAssets: ReturnType<typeof asset>[]): ExerciseDetail {
  return {
    body_region: "upper_body",
    difficulty: "beginner",
    equipment: ["dumbbell"],
    exercise_type: "compound",
    id: "incline-press",
    instructions_en: ["Press the dumbbells upward."],
    instructions_fa: ["دمبل‌ها را به سمت بالا فشار بده."],
    labels: [],
    media_assets: mediaAssets,
    media_attribution: null,
    media_path: mediaAssets[0]?.media_path ?? "",
    media_presentation: mediaAssets[0]?.presentation ?? null,
    media_type: "video",
    muscle_focus: "upper_chest",
    name_en: "Dumbbell Incline Bench Press",
    name_fa: "پرس بالا سینه دمبل",
    primary_muscle: "chest",
    safety_notes_en: ["Use a controlled range."],
    safety_notes_fa: ["حرکت را کنترل‌شده انجام بده."],
    secondary_muscles: [],
    slug: "incline-press",
  } as unknown as ExerciseDetail;
}
