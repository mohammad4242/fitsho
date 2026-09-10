import { expect, it } from "vitest";

import {
  fiticianDirectionalIconName,
  fiticianIconName,
  fiticianIconNames,
} from "./icons";

it("keeps member navigation on a stable, renderable icon set", () => {
  expect(fiticianIconNames).toEqual(expect.arrayContaining([
    "home",
    "training",
    "nutrition",
    "profile",
    "more",
    "genderMale",
    "genderFemale",
    "arrowLeft",
    "arrowRight",
  ]));
  expect(fiticianIconName("home")).toBe("home-variant-outline");
  expect(fiticianIconName("training")).toBe("dumbbell");
  expect(fiticianIconName("nutrition")).toBe("silverware-fork-knife");
  expect(fiticianIconName("profile")).toBe("account-circle-outline");
  expect(fiticianIconName("more")).toBe("dots-horizontal");
  expect(fiticianIconName("genderMale")).toBe("gender-male");
  expect(fiticianIconName("genderFemale")).toBe("gender-female");
});

it("maps navigation semantics to the correct physical arrow in RTL", () => {
  expect(fiticianDirectionalIconName("back", "rtl")).toBe("arrowRight");
  expect(fiticianDirectionalIconName("forward", "rtl")).toBe("arrowLeft");
  expect(fiticianDirectionalIconName("back", "ltr")).toBe("arrowLeft");
  expect(fiticianDirectionalIconName("forward", "ltr")).toBe("arrowRight");
});
