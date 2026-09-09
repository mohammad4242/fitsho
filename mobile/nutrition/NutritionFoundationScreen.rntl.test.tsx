import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@tanstack/react-query", () => ({
  useMutation: jest.fn(() => ({ isPending: false, mutate: jest.fn() })),
  useQuery: jest.fn(() => ({
    data: null,
    error: null,
    isError: false,
    isFetching: false,
    isPending: false,
    isStale: false,
  })),
  useQueryClient: jest.fn(() => ({ invalidateQueries: jest.fn(), setQueryData: jest.fn() })),
}));
jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../platform/connectivity", () => ({
  connectivityMonitor: {
    getSnapshot: () => ({ status: "online" }),
    subscribe: jest.fn(() => jest.fn()),
  },
}));
jest.mock("./NutritionAdherenceSection", () => ({ NutritionAdherenceSection: () => null }));
jest.mock("./NutritionCatalogueSection", () => ({ NutritionCatalogueSection: () => null }));
jest.mock("./NutritionClinicalSection", () => ({ NutritionClinicalSection: () => null }));
jest.mock("./NutritionPlanSection", () => ({ NutritionPlanSection: () => null }));
jest.mock("./NutritionSummaryCard", () => ({ NutritionSummaryCard: () => null }));
jest.mock("./NutritionTrackingSection", () => ({ NutritionTrackingSection: () => null }));
jest.mock("./nutritionApi", () => ({ createNutritionApi: jest.fn() }));

import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createNutritionApi } from "./nutritionApi";
import { NutritionFoundationScreen } from "./NutritionFoundationScreen";

const mockPush = jest.fn();
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockCreateNutritionApi = jest.mocked(createNutritionApi);

beforeEach(() => {
  mockPush.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
  mockUseMobileAuth.mockReturnValue({ request: jest.fn() } as never);
  mockCreateNutritionApi.mockReturnValue({
    getCurrentEstimate: jest.fn(),
    getNutritionProfile: jest.fn(),
    getReviewRequirement: jest.fn(),
    getSafety: jest.fn(),
    getStructuredExercise: jest.fn(),
  } as never);
});

test("keeps only web-equivalent daily navigation actions above the nutrition summary", () => {
  render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 400, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <NutritionFoundationScreen />
    </SafeAreaProvider>,
  );

  expect(screen.getByRole("button", { name: "ثبت تغذیه" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "کاتالوگ" })).toBeTruthy();
  expect(screen.getByText("هنوز برآوردی ثبت نشده")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "برنامه غذایی" })).toBeNull();

  fireEvent.press(screen.getByRole("button", { name: "ثبت تغذیه" }));
  expect(mockPush).toHaveBeenCalledWith("/member/nutrition-tracking");
  fireEvent.press(screen.getByRole("button", { name: "کاتالوگ" }));
  expect(mockPush).toHaveBeenCalledWith("/member/food-catalogue");

});
