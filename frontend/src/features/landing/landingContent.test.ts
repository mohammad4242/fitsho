import { expect, it } from "vitest";

import { landingScenes } from "./landingContent";

it("defines the three approved landing chapters", () => {
  expect(
    landingScenes.map(({ id, title, preload }) => ({ id, title, preload })),
  ).toEqual([
    { id: "strength", title: "از امروز، قوی‌تر.", preload: "metadata" },
    { id: "plan", title: "بدون حدس، با برنامه.", preload: "none" },
    { id: "progress", title: "هر تکرار، نزدیک‌تر.", preload: "none" },
  ]);
});
