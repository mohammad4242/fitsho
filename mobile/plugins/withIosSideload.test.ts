import { expect, it } from "vitest";

import {
  IOS_SIDELOAD_DISABLED_CAPABILITIES,
  stripIosSideloadEntitlements,
} from "./withIosSideload";

it("removes only provisioning-dependent entitlements for sideload builds", () => {
  const result = stripIosSideloadEntitlements({
    "aps-environment": "development",
    "com.apple.developer.applesignin": ["Default"],
    "com.apple.developer.associated-domains": ["applinks:app.fitician.example"],
    "keychain-access-groups": ["com.fitician.app"],
    customEntitlement: true,
  });

  expect(IOS_SIDELOAD_DISABLED_CAPABILITIES).toEqual([
    "aps-environment",
    "com.apple.developer.applesignin",
    "com.apple.developer.associated-domains",
  ]);
  expect(result).toEqual({
    "keychain-access-groups": ["com.fitician.app"],
    customEntitlement: true,
  });
});

it("does not change normal entitlements unless the sideload plugin is applied", () => {
  const normalEntitlements = {
    "aps-environment": "production",
    "com.apple.developer.applesignin": ["Default"],
    "com.apple.developer.associated-domains": ["applinks:app.fitician.example"],
  };

  expect({ ...normalEntitlements }).toEqual(normalEntitlements);
  expect(stripIosSideloadEntitlements({})).toEqual({});
});
