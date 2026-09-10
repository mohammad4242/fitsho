import { render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("expo-file-system", () => ({ File: class {} }));
jest.mock("expo-image-picker", () => ({ launchImageLibraryAsync: jest.fn() }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));
jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("react-native-worklets", () => ({ scheduleOnRN: jest.fn() }));
jest.mock("react-native-vision-camera", () => ({
  Camera: () => null,
  useCameraDevice: jest.fn(() => undefined),
  useCameraPermission: jest.fn(() => ({ canRequestPermission: true, hasPermission: false, requestPermission: jest.fn() })),
  useFrameOutput: jest.fn(() => ({})),
  usePhotoOutput: jest.fn(() => ({ capturePhotoToFile: jest.fn() })),
}));
jest.mock("../ui/navigation/BackBehaviorProvider", () => ({ useAndroidBackHandler: jest.fn() }));
jest.mock("./nativeBodyVision", () => ({ getNativeBodyVision: jest.fn(() => null), validateNativeBodyVisionResult: jest.fn() }));
jest.mock("./bodyPhotoEncoder", () => ({ encodeBodyPhotoWithPrivacyCrop: jest.fn() }));

import { BodyPhotoCapture } from "./BodyPhotoCapture";

const noopCapture = jest.fn<() => void>();

function renderCapture() {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <BodyPhotoCapture
        completedViews={["front"]}
        onCancel={jest.fn()}
        onCaptured={noopCapture}
        sex="male"
        view="side"
      />
    </SafeAreaProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("matches the web upload-first capture hierarchy", () => {
  renderCapture();

  expect(screen.getByRole("header", { name: "عکس‌های استاندارد بدن را اضافه کن" })).toBeTruthy();
  expect(screen.getByLabelText("لباس و پوشش مناسب")).toBeTruthy();
  expect(screen.getByLabelText("مراحل ثبت عکس")).toBeTruthy();
  expect(screen.getByLabelText("نمای نیمرخ، مرحله فعلی")).toBeTruthy();
  expect(screen.getByLabelText("نمای روبه‌رو، انجام‌شده")).toBeTruthy();
  expect(screen.getByLabelText("راهنمای کادر عکس Ghost")).toBeTruthy();
  expect(screen.getAllByText("عکس را زیر راهنمای Ghost قرار بده").length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "استفاده از دوربین راهنما" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "بارگذاری عکس نیمرخ" })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: "دوربین" })).toBeNull();
  expect(screen.queryByRole("radio", { name: "انتخاب عکس" })).toBeNull();
  expect(screen.queryByText("دسترسی دوربین لازم است")).toBeNull();
});
