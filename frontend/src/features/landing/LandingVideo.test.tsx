import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { landingScenes } from "./landingContent";
import { LandingVideo } from "./LandingVideo";

const play = vi.fn<() => Promise<void>>().mockResolvedValue(undefined);
const pause = vi.fn();

beforeEach(() => {
  play.mockClear();
  pause.mockClear();
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(play);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(pause);
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("plays the active scene without reduced motion", async () => {
  render(<LandingVideo scene={landingScenes[0]} active reducedMotion={false} />);

  expect(await screen.findByTestId("landing-video-strength")).toHaveAttribute(
    "preload",
    "metadata",
  );
  expect(play).toHaveBeenCalledOnce();
});

it("pauses an inactive scene", () => {
  render(<LandingVideo scene={landingScenes[1]} active={false} reducedMotion={false} />);

  expect(screen.getByTestId("landing-video-plan")).toHaveAttribute("preload", "none");
  expect(play).not.toHaveBeenCalled();
  expect(pause).toHaveBeenCalledOnce();
});

it("uses the mapped still image when reduced motion is enabled", () => {
  render(<LandingVideo scene={landingScenes[1]} active reducedMotion />);

  expect(screen.getByRole("img", { name: "بدون حدس، با برنامه." })).toBeVisible();
  expect(screen.queryByTestId("landing-video-plan")).not.toBeInTheDocument();
});
