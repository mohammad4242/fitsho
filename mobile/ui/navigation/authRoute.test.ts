import { expect, it } from "vitest";

import { isTokenAuthPath } from "./authRoute";

it("keeps verification and reset token screens reachable for signed-in users", () => {
  expect(isTokenAuthPath("/auth/verify-email")).toBe(true);
  expect(isTokenAuthPath("/auth/reset-password")).toBe(true);
  expect(isTokenAuthPath("/auth/sign-in")).toBe(false);
  expect(isTokenAuthPath("/auth/register")).toBe(false);
  expect(isTokenAuthPath("/verify-email")).toBe(false);
});
