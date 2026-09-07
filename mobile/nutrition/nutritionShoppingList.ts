import type { components } from "@fitician/core";

export type ShoppingListResponse = components["schemas"]["ShoppingListResponse"];
export type ShoppingListItemResponse = components["schemas"]["ShoppingListItemResponse"];
export type ShoppingListItem = Omit<ShoppingListItemResponse, "price_snapshot">;
export type ShoppingList = Omit<ShoppingListResponse, "items"> & {
  readonly items: ShoppingListItem[];
};

export type ShoppingPriceVisibility = "approved" | "not_approved" | "not_executable";

export function toPublicShoppingList(response: ShoppingListResponse): ShoppingList {
  return {
    ...response,
    items: response.items.map((item) => {
      const { price_snapshot, ...publicItem } = item;
      void price_snapshot;
      return publicItem;
    }),
  };
}

export function approvedShoppingPriceVisibility(
  list: Pick<ShoppingListResponse, "approval_status">,
  executable: boolean,
): ShoppingPriceVisibility {
  if (list.approval_status !== "approved") return "not_approved";
  return executable ? "approved" : "not_executable";
}

export function formatShoppingQuantity(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(value);
}
