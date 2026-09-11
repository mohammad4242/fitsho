import { expect, it } from "vitest";

import {
  appleCredentialFromResult,
  appleResultMessage,
} from "./appleCredential";

it("keeps the Apple identity token, nonce, and first-use profile data", () => {
  expect(
    appleCredentialFromResult(
      {
        email: "member@privaterelay.appleid.com",
        fullName: { familyName: "Member", givenName: "Fitician" },
        identityToken: "signed-apple-token",
      },
      "nonce-1",
    ),
  ).toEqual({
    email: "member@privaterelay.appleid.com",
    fullName: "Fitician Member",
    identityToken: "signed-apple-token",
    nonce: "nonce-1",
  });
});
it("rejects a successful Apple result without an identity token", () => {
  expect(
    appleCredentialFromResult({ email: null, fullName: null, identityToken: null }, "nonce-1"),
  ).toBeNull();
});

it("maps Apple cancellation and failure to safe Persian messages", () => {
  expect(appleResultMessage({ code: "ERR_REQUEST_CANCELED" })).toBe("ورود با اپل لغو شد.");
  expect(appleResultMessage({ code: "ERR_UNKNOWN" })).toBe("ورود با اپل انجام نشد. دوباره تلاش کنید.");
});
