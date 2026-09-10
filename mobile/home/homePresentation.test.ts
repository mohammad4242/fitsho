import { readFile } from "node:fs/promises";

import { describe, expect, it } from "vitest";

import { getHomeHeroLayout, getQuickActionColumns } from "./homePresentation";

describe("getHomeHeroLayout", () => {
  it("keeps exercise media beside the workout title on supported phones", () => {
    expect(getHomeHeroLayout(319)).toBe("stacked");
    expect(getHomeHeroLayout(320)).toBe("split");
    expect(getHomeHeroLayout(360)).toBe("split");
    expect(getHomeHeroLayout(430)).toBe("split");
  });
});

describe("getQuickActionColumns", () => {
  it("keeps image actions readable on the smallest supported phone", () => {
    expect(getQuickActionColumns(320)).toBe(1);
    expect(getQuickActionColumns(360)).toBe(2);
    expect(getQuickActionColumns(430)).toBe(2);
  });
});

it("places quick actions directly after nutrition without extra section headings", async () => {
  const source = await readFile(new URL("./MemberHomeScreen.tsx", import.meta.url), "utf8");

  expect(source).not.toContain('eyebrow="ادامه مسیر"');
  expect(source).not.toContain('title="دسترسی سریع"');
  expect(source).not.toContain("<SectionHeader");
});
