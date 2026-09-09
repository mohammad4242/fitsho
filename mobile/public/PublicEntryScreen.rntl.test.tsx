import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import { useRouter } from "expo-router";

import PublicEntryScreen from "../app/(public)/index";

const mockPush = jest.fn();
const mockUseRouter = jest.mocked(useRouter);

function renderEntry() {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 360, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      <PublicEntryScreen />
    </SafeAreaProvider>,
  );
}

beforeEach(() => {
  mockPush.mockClear();
  mockUseRouter.mockReturnValue({ push: mockPush } as never);
});

test("keeps the Web hero hierarchy in a concise native entry", () => {
  renderEntry();

  expect(screen.getByText("بدن تو، نقطه شروع برنامه")).toBeTruthy();
  expect(screen.getByRole("header", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeTruthy();
  expect(screen.getByText("تمرین و تغذیه‌ای متناسب با بدن، هدف و مسیر تو.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "برنامه من را بساز" })).toBeTruthy();
  expect(screen.getByTestId("public-entry-process")).toBeTruthy();
  expect(screen.getByText("فیتشو چگونه برنامه تو را می‌سازد")).toBeTruthy();
  expect(screen.getByText("تو را می‌شناسیم")).toBeTruthy();
  expect(screen.getByText("همراه پیشرفتت تنظیم می‌کنیم")).toBeTruthy();
});

test("keeps native entry actions connected to public onboarding and auth", () => {
  renderEntry();

  fireEvent.press(screen.getByRole("button", { name: "برنامه من را بساز" }));
  fireEvent.press(screen.getByRole("button", { name: "ورود به حساب" }));
  fireEvent.press(screen.getByRole("button", { name: "ساخت حساب جدید" }));

  expect(mockPush.mock.calls).toEqual([
    ["/public-onboarding"],
    ["/auth/sign-in"],
    ["/auth/register"],
  ]);
});
