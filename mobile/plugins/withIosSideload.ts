import { withEntitlementsPlist } from "expo/config-plugins";
import type { ConfigPlugin } from "expo/config-plugins";
import type { JSONValue } from "@expo/json-file";

/**
 * Capabilities that require a paid team's provisioning support when an IPA is
 * re-signed with a free Apple Account.
 */
export const IOS_SIDELOAD_DISABLED_CAPABILITIES = Object.freeze([
  "aps-environment",
  "com.apple.developer.applesignin",
  "com.apple.developer.associated-domains",
]);

type Entitlements = Record<string, JSONValue | undefined>;

export function stripIosSideloadEntitlements(entitlements: Entitlements): Entitlements {
  const result = { ...entitlements };
  for (const capability of IOS_SIDELOAD_DISABLED_CAPABILITIES) {
    delete result[capability];
  }
  return result;
}

const withIosSideloadEntitlements: ConfigPlugin = (config) => withEntitlementsPlist(config, (mod) => {
  mod.modResults = stripIosSideloadEntitlements(mod.modResults);
  return mod;
});

export default withIosSideloadEntitlements;
