import { expect, it } from "vitest";

import { redactLogData, redactLogMessage } from "./logging";

it("redacts tokens, credentials, identifiers, and sensitive media fields", () => {
  expect(redactLogData({
    access_token: "access-secret",
    email: "member@example.com",
    event: "upload_failed",
    image_uri: "file:///private/body.jpg",
    phone_number: "+989121234567",
  })).toEqual({
    access_token: "[REDACTED]",
    email: "[REDACTED]",
    event: "upload_failed",
    image_uri: "[REDACTED]",
    phone_number: "[REDACTED]",
  });
});

it("removes bearer and cookie values from arbitrary error text", () => {
  expect(redactLogMessage(
    "Bearer access-secret Cookie=fitician.auth.refresh-token=refresh-secret email=member@example.com",
  )).toBe("Bearer [REDACTED] Cookie=[REDACTED] email=[REDACTED]");
});
