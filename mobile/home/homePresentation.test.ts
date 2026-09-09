import { describe, expect, it } from "vitest";

import { getHomeHeroLayout, getQuickActionColumns } from "./homePresentation";

describe("getHomeHeroLayout", () => {
  it("stacks dense workout content only on narrow phones", () => {
    expect(getHomeHeroLayout(320)).toBe("stacked");
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
