import { normalizeMemberDeepLinkPath } from "../ui/navigation/deepLinks";

export async function redirectSystemPath(intent: { path: string; initial: boolean }): Promise<string> {
  return normalizeMemberDeepLinkPath(intent.path);
}
