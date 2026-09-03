import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { LivePoseGuideFactory } from "./livePoseGuide";
import { GhostCameraCapture, type CameraFallbackReason } from "./GhostCameraCapture";
import type { BodyPhotoSide, BodyPhotoView } from "./types";

const track = { stop: vi.fn() };
const getUserMedia = vi.fn();
const closeLiveGuide = vi.fn();
const livePoseGuideFactory: LivePoseGuideFactory = vi.fn().mockResolvedValue({
  check: vi.fn().mockReturnValue({ status: "available", warnings: [] }),
  close: closeLiveGuide,
});

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", {
    configurable: true,
    value,
  });
}

function prepareVideo() {
  const video = screen.getByLabelText(/live camera preview/i);
  Object.defineProperties(video, {
    videoWidth: { configurable: true, value: 1280 },
    videoHeight: { configurable: true, value: 1920 },
    readyState: { configurable: true, value: 4 },
  });
  fireEvent.loadedMetadata(video);
  return video;
}

function renderCamera(
  onFileCaptured = vi.fn().mockResolvedValue(undefined),
  sideProfile: BodyPhotoSide = "right",
  view: BodyPhotoView = "front",
) {
  const onFallback = vi.fn<(reason: CameraFallbackReason) => void>();
  const rendered = render(
    <GhostCameraCapture
      view={view}
      sideProfile={sideProfile}
      onFileCaptured={onFileCaptured}
      onFallback={onFallback}
      onClose={vi.fn()}
      livePoseGuideFactory={livePoseGuideFactory}
    />,
  );
  return { ...rendered, onFallback, onFileCaptured };
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  setSecureContext(true);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia,
      getSupportedConstraints: () => ({ facingMode: true }),
    },
  });
  getUserMedia.mockResolvedValue({ getTracks: () => [track] });
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:camera-preview");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it("falls back to upload in an insecure context", async () => {
  setSecureContext(false);
  const { onFallback } = renderCamera();

  await waitFor(() => expect(onFallback).toHaveBeenCalledWith("insecure_context"));
  expect(getUserMedia).not.toHaveBeenCalled();
});

it("falls back to upload when camera permission is denied", async () => {
  getUserMedia.mockRejectedValueOnce(new DOMException("denied", "NotAllowedError"));
  const { onFallback } = renderCamera();

  await waitFor(() => expect(onFallback).toHaveBeenCalledWith("permission_denied"));
});

it("falls back to upload when the browser has no camera capability", async () => {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: undefined,
  });
  const { onFallback } = renderCamera();

  await waitFor(() => expect(onFallback).toHaveBeenCalledWith("unsupported"));
});

it("stops the stream and live guide when the camera closes", async () => {
  const rendered = renderCamera();
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledWith({
    audio: false,
    video: {
      facingMode: { ideal: "user" },
      width: { ideal: 1280 },
      height: { ideal: 1920 },
    },
  }));
  prepareVideo();

  rendered.unmount();

  expect(track.stop).toHaveBeenCalled();
  await waitFor(() => expect(closeLiveGuide).toHaveBeenCalled());
});

it("toggles to the environment camera and stops the previous stream", async () => {
  const rendered = renderCamera();
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
  prepareVideo();

  fireEvent.click(screen.getByRole("button", { name: /environment camera/i }));
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(2));

  expect(getUserMedia.mock.calls[1]?.[0]).toEqual(expect.objectContaining({
    video: expect.objectContaining({ facingMode: { ideal: "environment" } }),
  }));
  expect(track.stop).toHaveBeenCalled();
  rendered.unmount();
});

it("changes only the centered Ghost size in uniform five-percent steps", () => {
  const rendered = renderCamera();
  const video = screen.getByLabelText(/live camera preview/i);
  const frame = rendered.container.querySelector<HTMLElement>(".ghost-overlay__asset-frame");
  const smaller = screen.getByRole("button", { name: /make ghost smaller/i });
  const larger = screen.getByRole("button", { name: /make ghost larger/i });

  expect(frame).not.toBeNull();
  if (frame === null) throw new Error("Ghost frame was not rendered");
  const initialVideoClass = video.className;

  fireEvent.click(smaller);
  expect(frame).toHaveStyle({ transform: "scale(0.95)" });
  expect(video.className).toBe(initialVideoClass);

  for (let click = 0; click < 4; click += 1) fireEvent.click(smaller);
  expect(frame).toHaveStyle({ transform: "scale(0.75)" });
  expect(smaller).toBeDisabled();

  for (let click = 0; click < 8; click += 1) fireEvent.click(larger);
  expect(frame).toHaveStyle({ transform: "scale(1.15)" });
  expect(larger).toBeDisabled();

  rendered.unmount();
});

it("shows the left side Ghost in guided camera mode", () => {
  const { container, unmount } = renderCamera(
    vi.fn().mockResolvedValue(undefined),
    "left",
    "side",
  );

  expect(container.querySelector(".ghost-overlay__asset-frame")).toHaveStyle({
    transform: "scaleX(-1) scale(1)",
  });
  unmount();
});

it("captures the transformed privacy crop, mirrors the user camera, and returns a JPEG file", async () => {
  const drawImage = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    restore: vi.fn(),
    drawImage,
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
    callback(new Blob(["camera-jpeg"], { type: "image/jpeg" }));
  });
  const onFileCaptured = vi.fn().mockResolvedValue(undefined);
  const rendered = renderCamera(onFileCaptured);
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
  const video = prepareVideo();
  await waitFor(() => expect(screen.getByRole("button", { name: /start five-second timer/i })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: /make ghost smaller/i }));
  vi.useFakeTimers();

  fireEvent.click(screen.getByRole("button", { name: /start five-second timer/i }));
  await act(async () => undefined);
  for (let second = 0; second < 5; second += 1) {
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
  }

  const canvas = document.querySelector("canvas");
  expect(canvas).not.toBeNull();
  expect(canvas).toHaveProperty("width", 1280);
  expect(canvas).toHaveProperty("height", 1580);
  expect(drawImage).toHaveBeenCalledWith(video, 0, 340, 1280, 1580, 0, 0, 1280, 1580);
  expect(screen.getByRole("button", { name: /use this camera photo/i })).toBeInTheDocument();

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /use this camera photo/i }));
  });
  expect(onFileCaptured).toHaveBeenCalledWith(expect.objectContaining({
    name: expect.stringMatching(/body-camera-front-.*\.jpg/),
    type: "image/jpeg",
  }));
  rendered.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:camera-preview");
});

it("captures the higher privacy crop for a back photo", async () => {
  const drawImage = vi.fn();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    save: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    restore: vi.fn(),
    drawImage,
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
    callback(new Blob(["camera-jpeg"], { type: "image/jpeg" }));
  });
  const rendered = renderCamera(
    vi.fn().mockResolvedValue(undefined),
    "right",
    "back",
  );
  await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
  const video = prepareVideo();
  await waitFor(() => expect(screen.getByRole("button", { name: /start five-second timer/i })).toBeEnabled());
  vi.useFakeTimers();

  fireEvent.click(screen.getByRole("button", { name: /start five-second timer/i }));
  await act(async () => undefined);
  for (let second = 0; second < 5; second += 1) {
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
  }

  const canvas = document.querySelector("canvas");
  expect(canvas).not.toBeNull();
  expect(canvas).toHaveProperty("width", 1280);
  expect(canvas).toHaveProperty("height", 1766);
  expect(drawImage).toHaveBeenCalledWith(video, 0, 154, 1280, 1766, 0, 0, 1280, 1766);

  rendered.unmount();
});
