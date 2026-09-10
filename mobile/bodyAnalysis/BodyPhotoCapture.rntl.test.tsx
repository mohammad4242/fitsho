import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
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
jest.mock("./nativeGhostPhotoRenderer", () => ({ renderNativeGhostPhoto: jest.fn() }));

import { BodyPhotoCapture } from "./BodyPhotoCapture";
import { launchImageLibraryAsync } from "expo-image-picker";
import { renderNativeGhostPhoto } from "./nativeGhostPhotoRenderer";
import type { BodyPhotoCapturedAsset } from "./cameraCapture";
import { ApiError } from "@fitician/core";

const selectedLibraryAsset = {
  height: 2400,
  mimeType: "image/jpeg",
  uri: "file:///cache/body-source.jpg",
  width: 1600,
};

const renderedAsset: BodyPhotoCapturedAsset = {
  height: 1656,
  mimeType: "image/jpeg",
  privacyCropApplied: true,
  source: "library",
  uri: "file:///cache/body-edited.jpg",
  width: 1200,
};

const noopCapture = jest.fn<(asset: BodyPhotoCapturedAsset) => void>();

function renderCapture(onCaptured: (asset: BodyPhotoCapturedAsset) => void | Promise<void> = noopCapture) {
  return render(
    <SafeAreaProvider initialMetrics={{
      frame: { height: 800, width: 390, x: 0, y: 0 },
      insets: { bottom: 0, left: 0, right: 0, top: 0 },
    }}>
      <BodyPhotoCapture
        completedViews={["front"]}
        onCancel={jest.fn()}
        onCaptured={onCaptured}
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

test("opens the web-parity editor after a gallery selection and keeps Ghost resizing independent", async () => {
  jest.mocked(launchImageLibraryAsync).mockResolvedValue({
    canceled: false,
    assets: [selectedLibraryAsset],
  });
  jest.mocked(renderNativeGhostPhoto).mockResolvedValue(renderedAsset);

  renderCapture();
  fireEvent.press(screen.getByRole("button", { name: "بارگذاری عکس نیمرخ" }));

  await waitFor(() => expect(screen.getByLabelText("ویرایشگر کادر عکس")).toBeTruthy());
  expect(screen.getByText("عکس را در قالب قرار بده")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "کوچک‌تر کردن Ghost" }));
  expect(screen.getByRole("button", { name: "کوچک‌تر کردن Ghost" })).toBeTruthy();
  expect(renderNativeGhostPhoto).not.toHaveBeenCalled();

  fireEvent.press(screen.getByRole("button", { name: "بزرگ‌نمایی عکس" }));
  fireEvent.press(screen.getByRole("button", { name: "چرخش عکس به راست" }));

  fireEvent.press(screen.getByRole("button", { name: "استفاده از این عکس" }));
  await waitFor(() => expect(renderNativeGhostPhoto).toHaveBeenCalledWith(expect.objectContaining({
    ghostScale: 0.95,
    source: "library",
    transform: expect.objectContaining({ rotation: 1, scale: 1.1 }),
    uri: selectedLibraryAsset.uri,
    view: "side",
  })));
  await waitFor(() => expect(noopCapture).toHaveBeenCalledWith(renderedAsset));
});

test("keeps the editor open and shows a preparation error when the native renderer fails", async () => {
  jest.mocked(launchImageLibraryAsync).mockResolvedValue({
    canceled: false,
    assets: [selectedLibraryAsset],
  });
  jest.mocked(renderNativeGhostPhoto).mockRejectedValueOnce(new Error("native render failed"));

  renderCapture();
  fireEvent.press(screen.getByRole("button", { name: "بارگذاری عکس نیمرخ" }));
  await waitFor(() => expect(screen.getByLabelText("ویرایشگر کادر عکس")).toBeTruthy());
  fireEvent.press(screen.getByRole("button", { name: "استفاده از این عکس" }));

  await waitFor(() => expect(screen.getByText("این عکس آماده نشد. عکس دیگری انتخاب کن یا دوباره تلاش کن.")).toBeTruthy());
  expect(screen.getByLabelText("ویرایشگر کادر عکس")).toBeTruthy();
});

test("keeps the selected editor state and reports an upload failure separately", async () => {
  const onCaptured = jest.fn<(asset: BodyPhotoCapturedAsset) => Promise<void>>();
  onCaptured.mockRejectedValue(new ApiError(500, "upload rejected"));
  jest.mocked(launchImageLibraryAsync).mockResolvedValue({
    canceled: false,
    assets: [selectedLibraryAsset],
  });
  jest.mocked(renderNativeGhostPhoto).mockResolvedValue(renderedAsset);

  renderCapture(onCaptured);
  fireEvent.press(screen.getByRole("button", { name: "بارگذاری عکس نیمرخ" }));
  await waitFor(() => expect(screen.getByLabelText("ویرایشگر کادر عکس")).toBeTruthy());
  fireEvent.press(screen.getByRole("button", { name: "استفاده از این عکس" }));

  await waitFor(() => expect(screen.getByText("سرویس ثبت عکس موقتاً در دسترس نیست. دوباره تلاش کن.")).toBeTruthy());
  expect(screen.getByLabelText("ویرایشگر کادر عکس")).toBeTruthy();
  expect(onCaptured).toHaveBeenCalledWith(renderedAsset);
});
