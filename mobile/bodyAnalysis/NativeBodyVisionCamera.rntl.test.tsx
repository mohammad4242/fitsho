import { act, render } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";

jest.mock("react-native-worklets", () => ({ scheduleOnRN: jest.fn() }));
jest.mock("react-native-vision-camera", () => ({
  Camera: jest.fn(() => null),
  useFrameOutput: jest.fn(() => ({ id: "body-vision-frame-output" })),
}));

import { scheduleOnRN } from "react-native-worklets";
import { Camera, useFrameOutput } from "react-native-vision-camera";
import type { FiticianBodyVision } from "@fitician/body-vision";
import { NativeBodyVisionCamera } from "./NativeBodyVisionCamera";

const photoOutput = { id: "photo-output" } as never;
const device = { id: "front-camera" } as never;

type NativeVisionMock = {
  readonly contractVersion: string;
  readonly modelStatus: string;
  readonly process: jest.Mock;
  readonly recordDroppedFrame: jest.Mock;
  readonly benchmark: jest.Mock;
};

function createNativeVision(): NativeVisionMock {
  return {
    contractVersion: "1.0",
    modelStatus: "ready",
    process: jest.fn(),
    recordDroppedFrame: jest.fn(),
    benchmark: jest.fn(),
  };
}

beforeEach(() => {
  jest.clearAllMocks();
});

test("connects photo and native vision outputs and forwards processed frames", () => {
  const nativeVision = createNativeVision();
  const result = { frame: { timestamp: 2 }, landmarks: [], mask: {} };
  nativeVision.process.mockReturnValue(result);
  const onNativeResult = jest.fn();

  render(
    <NativeBodyVisionCamera
      device={device}
      isActive
      nativeVision={nativeVision as unknown as FiticianBodyVision}
      onError={jest.fn()}
      onNativeResult={onNativeResult}
      onPreviewStarted={jest.fn()}
      onPreviewStopped={jest.fn()}
      photoOutput={photoOutput}
    />,
  );

  const cameraProps = jest.mocked(Camera).mock.calls.at(-1)?.[0] as unknown as Record<string, unknown>;
  expect(cameraProps.outputs).toEqual([photoOutput, { id: "body-vision-frame-output" }]);
  expect(cameraProps.isActive).toBe(true);

  const frameOutputOptions = jest.mocked(useFrameOutput).mock.calls.at(-1)?.[0] as {
    onFrame?: (frame: { dispose: () => void }) => void;
  };
  const frame = { dispose: jest.fn() };
  act(() => frameOutputOptions.onFrame?.(frame));

  expect(nativeVision.process).toHaveBeenCalledWith(frame);
  expect(frame.dispose).toHaveBeenCalledTimes(1);
  expect(scheduleOnRN).toHaveBeenCalledWith(onNativeResult, result);
});

test("disposes inactive frames and records dropped frames without processing them", () => {
  const nativeVision = createNativeVision();

  render(
    <NativeBodyVisionCamera
      device={device}
      isActive={false}
      nativeVision={nativeVision as unknown as FiticianBodyVision}
      onError={jest.fn()}
      onNativeResult={jest.fn()}
      onPreviewStarted={jest.fn()}
      onPreviewStopped={jest.fn()}
      photoOutput={photoOutput}
    />,
  );

  const frameOutputOptions = jest.mocked(useFrameOutput).mock.calls.at(-1)?.[0] as {
    onFrame?: (frame: { dispose: () => void }) => void;
    onFrameDropped?: () => void;
  };
  const frame = { dispose: jest.fn() };
  act(() => frameOutputOptions.onFrame?.(frame));
  act(() => frameOutputOptions.onFrameDropped?.());

  expect(nativeVision.process).not.toHaveBeenCalled();
  expect(nativeVision.recordDroppedFrame).toHaveBeenCalledTimes(1);
  expect(frame.dispose).toHaveBeenCalledTimes(1);
});
