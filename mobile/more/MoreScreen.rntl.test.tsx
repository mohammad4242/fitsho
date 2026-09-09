import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("../auth/MobileAuthProvider", () => ({ useMobileAuth: jest.fn() }));
jest.mock("../ui/navigation/RouteGuards", () => ({ useMobileRouteSnapshot: jest.fn() }));
jest.mock("../profile/profileApi", () => ({ createProfileApi: jest.fn() }));

import { useRouter } from "expo-router";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { createProfileApi } from "../profile/profileApi";
import { useMobileRouteSnapshot } from "../ui/navigation/RouteGuards";
import { MoreScreen } from "./MoreScreen";

const mockPush = jest.fn();
const mockUseRouter = jest.mocked(useRouter);
const mockUseMobileAuth = jest.mocked(useMobileAuth);
const mockUseRouteSnapshot = jest.mocked(useMobileRouteSnapshot);
const mockCreateProfileApi = jest.mocked(createProfileApi);
const mockLogout = jest.fn<() => Promise<void>>();
const mockReplace = jest.fn();

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
  mockReplace.mockClear();
  mockLogout.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush, replace: mockReplace } as never);
  mockUseMobileAuth.mockReturnValue({
    logout: mockLogout,
    request: jest.fn(),
    status: "signed_in",
    user: { email: "member@example.com", id: "member-1", phone_number: null },
  } as never);
  mockCreateProfileApi.mockReturnValue({
    getSharedProfile: jest.fn<() => Promise<null>>(() => new Promise(() => undefined)),
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
  expect(screen.getByRole("button", { name: "کاتالوگ مواد غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "کاتالوگ وعده‌های غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "تحلیل بدن" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "ثبت تغذیه" })).toBeTruthy();

  fireEvent.press(screen.getByRole("button", { name: "کتابخانه حرکات" }));
  fireEvent.press(screen.getByRole("button", { name: "تحلیل بدن" }));
  fireEvent.press(screen.getByRole("button", { name: "کاتالوگ مواد غذایی" }));
  fireEvent.press(screen.getByRole("button", { name: "کاتالوگ وعده‌های غذایی" }));
  fireEvent.press(screen.getByRole("button", { name: "ثبت تغذیه" }));

  expect(mockPush.mock.calls).toEqual([
    ["/member/exercises"],
    ["/member/body-analysis-history"],
    ["/member/food-catalogue"],
    ["/member/meal-catalogue"],
    ["/member/nutrition-tracking"],
  ]);
});

test("hides libraries outside the member product mode", () => {
  productMode = "training";
  renderMore();

  expect(screen.getByRole("button", { name: "کتابخانه حرکات" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "کاتالوگ مواد غذایی" })).toBeNull();
  expect(screen.queryByRole("button", { name: "کاتالوگ وعده‌های غذایی" })).toBeNull();
});

test("shows only nutrition libraries for a nutrition member", () => {
  productMode = "nutrition";
  renderMore();

  expect(screen.queryByRole("button", { name: "کتابخانه حرکات" })).toBeNull();
  expect(screen.getByRole("button", { name: "کاتالوگ مواد غذایی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "کاتالوگ وعده‌های غذایی" })).toBeTruthy();
});

test("shows account actions and specialist workspaces only for granted roles", () => {
  mockUseRouteSnapshot.mockReturnValue({
    profile: { completionState: "both_ready", productMode: "both", status: "resolved" },
    session: { status: "signed_in", user: { email: "member@example.com", id: "member-1" } },
    specialistAccess: { coach: "granted", physician: "denied" },
  } as never);

  renderMore();

  expect(screen.getByRole("header", { name: "حساب و حریم خصوصی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "اطلاعات پروفایل" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "حذف حساب" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "سیاست حریم خصوصی" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "فضاهای تخصصی" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "فضای مربی" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "فضای پزشک" })).toBeNull();
  expect(screen.queryByText("کتابخانه برنامه‌های تمرینی")).toBeNull();
});

test("logs out through the existing auth session and replaces the member route", async () => {
  mockLogout.mockResolvedValue(undefined);
  renderMore();

  fireEvent.press(screen.getByRole("button", { name: "خروج از حساب" }));

  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/auth/sign-in"));
  expect(mockLogout).toHaveBeenCalledTimes(1);
});
