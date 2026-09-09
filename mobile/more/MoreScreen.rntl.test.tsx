import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/navigation/RouteGuards", () => ({ useMobileRouteSnapshot: jest.fn() }));

import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { MoreScreen } from "./MoreScreen";

const mockPush = jest.fn();
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockUseRouteSnapshot = jest.mocked(useMobileRouteSnapshot);

let productMode: "both" | "training" | "nutrition" = "both";

function renderMore() {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 400, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <MoreScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  productMode = "both";
  mockPush.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
  mockUseMobileAuth.mockReturnValue({
    status: "signed_in",
    user: { email: "member@example.com", id: "member-1", phone_number: null },
  } as never);
  mockUseRouteSnapshot.mockImplementation(() => ({
    profile: { completionState: "both_ready", productMode, status: "resolved" },
    session: {
      status: "signed_in",
      user: { email: "member@example.com", id: "member-1", phone_number: null },
    },
    specialistAccess: { coach: "denied", physician: "denied" },
  } as never));
});

test("renders the More hub and routes the profile entry to the member profile", () => {
  renderMore();

  expect(screen.getByRole("header", { name: "بیشتر" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "پروفایل من" })).toBeTruthy();
  expect(screen.getByText("مشخصات و تنظیمات شخصی")).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "پروفایل من" }));

  expect(mockPush).toHaveBeenCalledWith("/member/profile");
});

test("shows and routes all supported secondary libraries", () => {
  renderMore();

  expect(screen.getByRole("button", { name: "کتابخانه حرکات" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "کتابخانه مواد غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "وعده‌های غذایی" })).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "کتابخانه حرکات" }));
  fireEvent.press(screen.getByRole("button", { name: "کتابخانه مواد غذایی" }));
  fireEvent.press(screen.getByRole("button", { name: "وعده‌های غذایی" }));

  expect(mockPush.mock.calls).toEqual([
    ["/member/exercises"],
    ["/member/food-catalogue"],
    ["/member/meal-catalogue"],
  ]);
});

test("hides libraries outside the member product mode", () => {
  productMode = "training";
  renderMore();

  expect(screen.getByRole("button", { name: "کتابخانه حرکات" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "کتابخانه مواد غذایی" })).toBeNull();
  expect(screen.queryByRole("button", { name: "وعده‌های غذایی" })).toBeNull();
});

test("shows only nutrition libraries for a nutrition member", () => {
  productMode = "nutrition";
  renderMore();

  expect(screen.queryByRole("button", { name: "کتابخانه حرکات" })).toBeNull();
  expect(screen.getByRole("button", { name: "کتابخانه مواد غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "وعده‌های غذایی" })).toBeTruthy();
});
