import { getMobileRuntimeConfig } from "../config/nativeRuntimeConfig";
import { normalizeNativeDeepLinkPath } from "../ui/navigation/deepLinks";

export async function redirectSystemPath(
  intent: { path: string; initial: boolean },
): Promise<string | null> {
  return normalizeNativeDeepLinkPath(intent.path, {
    appLinkHost: getMobileRuntimeConfig().appLinkHost,
  });
}
