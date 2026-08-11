import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { useSynchronizedProgress } from "./useSynchronizedProgress";

let callbacks: Map<number, FrameRequestCallback>;
let nextFrameId: number;
const cancelFrame = vi.fn();

function ProgressHarness() {
  const progress = useSynchronizedProgress(900);
  return <output data-testid="progress">{progress}</output>;
}

beforeEach(() => {
  callbacks = new Map();
  nextFrameId = 1;
  cancelFrame.mockReset();
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback: FrameRequestCallback) => {
    const frameId = nextFrameId;
    nextFrameId += 1;
    callbacks.set(frameId, callback);
    return frameId;
  }));
  vi.stubGlobal("cancelAnimationFrame", cancelFrame);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function runNextFrame(timestamp: number) {
  const entry = callbacks.entries().next().value as [number, FrameRequestCallback] | undefined;
  if (entry === undefined) throw new Error("No animation frame was queued");
  callbacks.delete(entry[0]);
  act(() => entry[1](timestamp));
}

it("starts at zero and reaches exactly one on a single frame timeline", () => {
  render(<ProgressHarness />);

  expect(screen.getByTestId("progress")).toHaveTextContent("0");

  runNextFrame(100);
  expect(screen.getByTestId("progress")).toHaveTextContent("0");

  runNextFrame(1_000);
  expect(screen.getByTestId("progress")).toHaveTextContent("1");
});

it("cancels its queued animation frame when unmounted", () => {
  const { unmount } = render(<ProgressHarness />);

  unmount();

  expect(cancelFrame).toHaveBeenCalledWith(1);
});

it("finishes immediately when reduced motion is requested", () => {
  vi.mocked(matchMedia).mockReturnValue({ matches: true } as MediaQueryList);

  render(<ProgressHarness />);

  expect(screen.getByTestId("progress")).toHaveTextContent("1");
  expect(requestAnimationFrame).not.toHaveBeenCalled();
});
