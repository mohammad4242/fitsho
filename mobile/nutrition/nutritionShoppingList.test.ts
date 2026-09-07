import { expect, it } from "vitest";

import type { components } from "@fitician/core";

import {
  approvedShoppingPriceVisibility,
  formatShoppingQuantity,
  toPublicShoppingList,
} from "./nutritionShoppingList";

const shoppingList = {
  approval_status: "approved",
  items: [
    {
      canonical_unit: "g",
      cost_irr: 1_250_000,
      food_id: "food-1",
      name_en: "Rice",
      name_fa: "برنج",
      nutrients: { energy_kcal: 2_100 },
      price_snapshot: { reference_id: "private-snapshot-id", candidate: 42 },
      required_quantity: 1_050.25,
      slug: "rice",
    },
  ],
  plan_id: "plan-1",
  plan_revision: 3,
  total_cost_irr: 1_250_000,
  warning_codes: [],
} as components["schemas"]["ShoppingListResponse"];

it("removes internal price snapshots before member presentation", () => {
  const publicList = toPublicShoppingList(shoppingList);

  expect(publicList.items[0]).toEqual({
    canonical_unit: "g",
    cost_irr: 1_250_000,
    food_id: "food-1",
    name_en: "Rice",
    name_fa: "برنج",
    nutrients: { energy_kcal: 2_100 },
    required_quantity: 1_050.25,
    slug: "rice",
  });
  expect(publicList.items[0]).not.toHaveProperty("price_snapshot");
});

it("shows shopping prices only for an executable approved plan", () => {
  expect(approvedShoppingPriceVisibility(shoppingList, true)).toBe("approved");
  expect(approvedShoppingPriceVisibility(shoppingList, false)).toBe("not_executable");
  expect(approvedShoppingPriceVisibility({ ...shoppingList, approval_status: "pending" }, true)).toBe("not_approved");
  expect(formatShoppingQuantity(1_050.25)).toBe("۱٬۰۵۰٫۳");
});
