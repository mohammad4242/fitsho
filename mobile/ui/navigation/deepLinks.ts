import { DEFAULT_APP_LINK_HOST } from "../../config/runtimeConfig";

const deepLinkBase = "fitician://app";
const nativeLinkHosts = new Set(["app", "auth", "link", "member"]);
const authSessionCallbackSchemes = new Set(["fitician:", "com.fitician.app:"]);

type MemberDeepLinkResource = "cycles" | "exercises" | "plans";

export function normalizeMemberDeepLinkPath(path: string): string {
  const parsed = parseDeepLink(path);
  if (parsed === null) return path;
  return normalizeMemberSegments(routeSegments(parsed)) ?? path;
}

export interface NativeDeepLinkOptions {
  readonly appLinkHost?: string;
}

export function normalizeNativeDeepLinkPath(
  path: string,
  options: NativeDeepLinkOptions = {},
): string | null {
  if (isExpoDevelopmentClientIntent(path)) return null;

  const parsed = parseDeepLink(path);
  if (parsed === null) return "/";
  if (isAuthSessionCallback(parsed)) return null;
  if (!isAllowedNativeLink(parsed, options.appLinkHost ?? DEFAULT_APP_LINK_HOST)) {
    return "/";
  }

  const segments = routeSegments(parsed);
  const memberPath = normalizeMemberSegments(segments);
  if (memberPath !== null) return memberPath;

  const authSegments = segments[0] === "auth" ? segments : ["auth", ...segments];
  if (authSegments.length !== 2) return "/";
  const authRoute = authSegments[1];
  if (authRoute !== "reset-password" && authRoute !== "verify-email") return "/";
  const tokens = parsed.searchParams.getAll("token");
  const token = tokens.length === 1 ? tokens[0]?.trim() : undefined;
  if (token === undefined || token.length === 0 || token.length > 512) return "/";
  return `/auth/${authRoute}?token=${encodeURIComponent(token)}`;
}

function isExpoDevelopmentClientIntent(path: string): boolean {
  try {
    const parsed = new URL(path);
    return parsed.protocol === "fitician:"
      && parsed.hostname === "expo-development-client"
      && parsed.pathname === "/"
      && parsed.searchParams.has("url");
  } catch {
    return false;
  }
}

function isAuthSessionCallback(parsed: URL): boolean {
  if (!authSessionCallbackSchemes.has(parsed.protocol)) return false;
  const isBundleCallback = parsed.protocol === "com.fitician.app:"
    && parsed.pathname === "/oauthredirect";
  const isFiticianCallback = parsed.protocol === "fitician:"
    && (parsed.pathname === "/oauthredirect" || parsed.hostname === "oauthredirect");
  if (!isBundleCallback && !isFiticianCallback) return false;
  return ["code", "id_token", "error", "state"].some((key) => parsed.searchParams.has(key));
}

function parseDeepLink(path: string): URL | null {
  try {
    return new URL(path, deepLinkBase);
  } catch {
    return null;
  }
}

function isAllowedNativeLink(parsed: URL, appLinkHost: string): boolean {
  if (parsed.protocol === "https:") {
    const host = appLinkHost.trim().toLowerCase();
    return parsed.hostname === host
      && (parsed.pathname === "/link" || parsed.pathname.startsWith("/link/"));
  }
  return parsed.protocol === "fitician:" && nativeLinkHosts.has(parsed.hostname);
}

function routeSegments(parsed: URL): string[] {
  const segments = parsed.pathname
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => decodeSegment(segment));
  const routeSegments = parsed.hostname === "member" || parsed.hostname === "auth"
    ? [parsed.hostname, ...segments]
    : segments;
  return routeSegments[0] === "link" ? routeSegments.slice(1) : routeSegments;
}

function normalizeMemberSegments(segments: readonly string[]): string | null {
  if (segments[0] !== "member") return null;
  const resource = segments[1] as MemberDeepLinkResource | undefined;
  const identifier = segments[2];
  if (
    identifier === undefined
    || segments.length !== 3
    || (resource !== "cycles" && resource !== "exercises" && resource !== "plans")
  ) {
    return null;
  }

  const encodedIdentifier = encodeURIComponent(identifier);
  if (resource === "exercises") {
    return `/member/exercises/${encodedIdentifier}`;
  }
  const queryName = resource === "plans" ? "planId" : "cycleId";
  return `/member/workouts?${queryName}=${encodedIdentifier}`;
}

function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}
