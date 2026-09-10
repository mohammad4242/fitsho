import { fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StyleSheet } from "react-native";
import type { ReactTestInstance } from "react-test-renderer";

jest.mock("expo-router", () => ({ useRouter: jest.fn() }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import { useRouter } from "expo-router";

import PublicEntryScreen from "../app/(public)/index";

const mockPush = jest.fn();
const mockUseRouter = jest.mocked(useRouter);

function findAncestorStyle(node: ReactTestInstance, key: string): Record<string, unknown> {
  let current = node.parent;
  while (current !== null) {
    const style = StyleSheet.flatten(current.props.style) as Record<string, unknown> | undefined;
    if (style?.[key] !== undefined) return style;
    current = current.parent;
  }
  throw new Error(`Ancestor style ${key} not found`);
}

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

  expect(screen.getByRole("header", { name: "هر بدن، برنامه خودش را می‌خواهد." })).toBeTruthy();
  expect(screen.getByText("تمرین و تغذیه‌ای متناسب با بدن، هدف و مسیر تو.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "برنامه من را بساز" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "برنامه تمرینی، تحت نظر مربی" })).toBeTruthy();
  expect(screen.getByRole("header", { name: "برنامه تغذیه، تحت نظر پزشک" })).toBeTruthy();
  expect(screen.getByText("MEAL PHOTO ANALYSIS")).toBeTruthy();
  expect(screen.getByTestId("public-entry-process")).toBeTruthy();
  expect(screen.getByText("فیتشو چگونه برنامه تو را می‌سازد")).toBeTruthy();
  expect(screen.getByText("تو را می‌شناسیم")).toBeTruthy();
  expect(screen.getByText("همراه پیشرفتت تنظیم می‌کنیم")).toBeTruthy();
  expect(findAncestorStyle(screen.getByText("تو را می‌شناسیم"), "flexDirection")).toMatchObject({ flexDirection: "row" });
});

test("keeps native entry actions connected to public onboarding and auth", () => {
  renderEntry();

  fireEvent.press(screen.getByRole("button", { name: "برنامه من را بساز" }));
  fireEvent.press(screen.getByRole("button", { name: "ورود" }));

  expect(mockPush.mock.calls).toEqual([
    ["/public-onboarding"],
    ["/auth/sign-in"],
  ]);
});
