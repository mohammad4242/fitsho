import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { MemberHeaderMedia } from "./MemberHeaderMedia";

const play = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
const pause = vi.fn();
let onIntersect: ((entries: IntersectionObserverEntry[]) => void) | undefined;

class HeaderIntersectionObserver {
  constructor(callback: (entries: IntersectionObserverEntry[]) => void) {
    onIntersect = callback;
  }

  observe() {}

  disconnect() {}
}

beforeEach(() => {
  play.mockClear();
  pause.mockClear();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(play);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(pause);
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false })));
  vi.stubGlobal("IntersectionObserver", HeaderIntersectionObserver);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it("plays a supplied video only after its header becomes visible", () => {
  render(<MemberHeaderMedia imageSrc="/still.jpg" videoSrc="/motion.mp4" />);

  expect(screen.getByTestId<HTMLVideoElement>("member-header-video").muted).toBe(true);
  expect(play).not.toHaveBeenCalled();

  act(() => onIntersect?.([{ isIntersecting: true } as IntersectionObserverEntry]));

  expect(play).toHaveBeenCalledOnce();
});

it("uses the still image when reduced motion is requested", () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));

  render(<MemberHeaderMedia imageSrc="/still.jpg" videoSrc="/motion.mp4" />);

  expect(screen.getByTestId("member-header-image")).toHaveAttribute("src", "/still.jpg");
  expect(screen.queryByTestId("member-header-video")).not.toBeInTheDocument();
});

it("does not play a visible video while its chapter is inactive", () => {
  render(<MemberHeaderMedia imageSrc="/still.jpg" videoSrc="/motion.mp4" active={false} />);

  act(() => onIntersect?.([{ isIntersecting: true } as IntersectionObserverEntry]));

  expect(play).not.toHaveBeenCalled();
  expect(pause).toHaveBeenCalled();
});
