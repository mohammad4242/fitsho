import { render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";

const mockUseIsFocused = jest.fn(() => true);

jest.mock("expo-router", () => ({
  useIsFocused: () => mockUseIsFocused(),
}));
jest.mock("expo-video", () => {
  const React = jest.requireActual("react") as typeof import("react");
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    useVideoPlayer: () => ({ addListener: jest.fn(), status: "idle" }),
    VideoView: (props: Record<string, unknown>) => React.createElement(View, { testID: "native-video", ...props }),
  };
});
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { ExerciseMedia } from "./ExerciseMedia";

beforeEach(() => {
  mockUseIsFocused.mockReturnValue(true);
});

test("releases the video subtree when its route loses focus", () => {
  const media = {
    accessibilityLabel: "رسانه حرکت",
    mediaType: "video" as const,
    name: "پرس بالا سینه دمبل",
    path: "/media/incline-press.mp4",
  };
  const { rerender } = render(<ExerciseMedia {...media} />);

  expect(screen.getByTestId("native-video")).toBeTruthy();

  mockUseIsFocused.mockReturnValue(false);
  rerender(<ExerciseMedia {...media} />);

  expect(screen.queryByTestId("native-video")).toBeNull();
});

test("keeps image media available when its route loses focus", () => {
  mockUseIsFocused.mockReturnValue(false);

  render(
    <ExerciseMedia
      accessibilityLabel="تصویر حرکت"
      mediaType="image"
      name="پرس بالا سینه دمبل"
      path="/media/incline-press.webp"
    />,
  );

  expect(screen.queryByTestId("native-video")).toBeNull();
  expect(screen.getByLabelText("تصویر حرکت")).toBeTruthy();
});

test("uses a real poster without mounting a deferred video player", () => {
  render(
    <ExerciseMedia
      accessibilityLabel="رسانه حرکت"
      deferVideo
      mediaType="video"
      name="پرس بالا سینه دمبل"
      path="/media/exercises/incline-press/media-abc.mp4"
    />,
  );

  expect(screen.queryByTestId("native-video")).toBeNull();
  expect(screen.getByLabelText("پوستر حرکت پرس بالا سینه دمبل")).toBeTruthy();
  expect(screen.queryByText("برای مشاهده، جزئیات حرکت را باز کن")).toBeNull();
});

test("mounts the deferred video only when its preview is active", () => {
  render(
    <ExerciseMedia
      accessibilityLabel="رسانه حرکت"
      deferVideo
      mediaType="video"
      name="پرس بالا سینه دمبل"
      path="/media/exercises/incline-press/media-abc.mp4"
      videoActive
    />,
  );

  expect(screen.getByTestId("native-video")).toBeTruthy();
  expect(screen.queryByLabelText("پوستر حرکت پرس بالا سینه دمبل")).toBeNull();
});
