import { expect, it } from "vitest";

import { fiticianIconName, fiticianIconNames } from "./icons";

it("keeps member navigation on a stable, renderable icon set", () => {
  expect(fiticianIconNames).toEqual(expect.arrayContaining([
    "home",
    "training",
    "nutrition",
    "profile",
  ]));
  expect(fiticianIconName("home")).toBe("home-variant-outline");
  expect(fiticianIconName("training")).toBe("dumbbell");
  expect(fiticianIconName("nutrition")).toBe("silverware-fork-knife");
  expect(fiticianIconName("profile")).toBe("account-circle-outline");
});
