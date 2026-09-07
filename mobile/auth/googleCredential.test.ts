import { expect, it } from "vitest";

import { googleCredentialFromResult, googleResultMessage } from "./googleCredential";

it("extracts only a non-empty Google ID token from a successful native result", () => {
  expect(
    googleCredentialFromResult({ params: { id_token: "signed-id-token" }, type: "success" }),
  ).toBe("signed-id-token");
  expect(googleCredentialFromResult({ params: {}, type: "success" })).toBeNull();
  expect(googleCredentialFromResult({ type: "cancel" })).toBeNull();
});

it("maps cancelled and failed Google prompts to safe messages", () => {
  expect(googleResultMessage({ type: "cancel" })).toBe("ورود با گوگل لغو شد.");
  expect(googleResultMessage({ errorCode: "access_denied", type: "error" })).toBe(
    "ورود با گوگل انجام نشد. دوباره تلاش کنید.",
  );
});
