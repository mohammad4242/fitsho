import { expect, it } from "vitest";

import type { User } from "@fitician/core/auth";

import { decideMobileRoute, defaultMobileRouteSnapshot } from "./navigation/routePolicy";

const user: User = {
  created_at: "2026-01-01T00:00:00Z",
  email: "member@example.com",
  id: "member-1",
  is_admin: false,
  phone_number: null,
};

it("allows account deletion for signed-in users before profile completion", () => {
  expect(decideMobileRoute("account", {
    ...defaultMobileRouteSnapshot,
    session: { status: "signed_in", user },
  })).toEqual({ status: "allow" });
});

it("keeps account deletion behind authentication", () => {
  expect(decideMobileRoute("account", defaultMobileRouteSnapshot)).toEqual({
    href: "/auth/sign-in",
    status: "redirect",
  });
});
