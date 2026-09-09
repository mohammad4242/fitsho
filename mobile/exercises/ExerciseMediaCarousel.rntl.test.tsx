import { act, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";

const mockVideoPlayer = {
  addListener: jest.fn(),
  status: "idle",
};

jest.mock("expo-video", () => {
  const React = jest.requireActual("react") as typeof import("react");
  const { View } = jest.requireActual("react-native") as typeof import("react-native");
  return {
    useVideoPlayer: (_source: unknown, setup?: (player: typeof mockVideoPlayer) => void) => {
      setup?.(mockVideoPlayer);
      return mockVideoPlayer;
    },
    VideoView: (props: Record<string, unknown>) => React.createElement(View, { testID: "native-video", ...props }),
  };
});
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { ExerciseMediaCarousel } from "./ExerciseMediaCarousel";
import type { ExerciseMediaItem } from "./exerciseMedia";

const items: ExerciseMediaItem[] = [
  {
    key: "male-demo-1",
    mediaAttribution: null,
    mediaPath: "/media/male-1.mp4",
    mediaType: "video",
    presentation: "male",
    sortOrder: 0,
  },
  {
    key: "male-demo-2",
    mediaAttribution: null,
    mediaPath: "/media/male-2.mp4",
    mediaType: "video",
    presentation: "male",
    sortOrder: 1,
  },
];

beforeEach(() => {
  mockVideoPlayer.addListener.mockClear();
});

test("mounts one current player and keeps pagination on the media surface", () => {
  const onIndexChange = jest.fn();
  const { rerender } = render(
    <ExerciseMediaCarousel
      apiBaseUrl="https://api.example.com"
      items={items}
      language="fa"
      name="پرس بالا سینه دمبل"
      onIndexChange={onIndexChange}
      selectedIndex={0}
    />,
  );

  expect(screen.getByTestId("exercise-media-surface")).toBeTruthy();
  expect(screen.getByText("1/2")).toBeTruthy();
  expect(screen.getAllByTestId("native-video")).toHaveLength(1);
  expect(screen.getByTestId("native-video").props.nativeControls).toBe(true);

  rerender(
    <ExerciseMediaCarousel
      apiBaseUrl="https://api.example.com"
      items={items}
      language="fa"
      name="پرس بالا سینه دمبل"
      onIndexChange={onIndexChange}
      selectedIndex={1}
    />,
  );

  expect(screen.getByText("2/2")).toBeTruthy();
  expect(screen.getAllByTestId("native-video")).toHaveLength(1);
});

test("hides single-item pagination and renders the clean missing-media state", () => {
  const onIndexChange = jest.fn();
  const { rerender } = render(
    <ExerciseMediaCarousel
      apiBaseUrl="https://api.example.com"
      items={[items[0]]}
      language="fa"
      name="پرس بالا سینه دمبل"
      onIndexChange={onIndexChange}
      selectedIndex={0}
    />,
  );

  expect(screen.queryByText("1/1")).toBeNull();

  rerender(
    <ExerciseMediaCarousel
      apiBaseUrl="https://api.example.com"
      items={[]}
      language="fa"
      name="پرس بالا سینه دمبل"
      onIndexChange={onIndexChange}
      selectedIndex={0}
    />,
  );

  expect(screen.getByText("رسانهٔ این حرکت در دسترس نیست.")).toBeTruthy();
  expect(screen.queryByTestId("native-video")).toBeNull();
});

test("falls back cleanly when the mounted video reports a load error", () => {
  render(
    <ExerciseMediaCarousel
      apiBaseUrl="https://api.example.com"
      items={[items[0]]}
      language="en"
      name="Dumbbell Incline Bench Press"
      onIndexChange={jest.fn()}
      selectedIndex={0}
    />,
  );

  const statusListener = mockVideoPlayer.addListener.mock.calls[0]?.[1] as
    | ((payload: { readonly status: string }) => void)
    | undefined;
  expect(statusListener).toBeDefined();

  act(() => statusListener?.({ status: "error" }));

  expect(screen.getByText("Exercise media is unavailable.")).toBeTruthy();
  expect(screen.queryByTestId("native-video")).toBeNull();
});
