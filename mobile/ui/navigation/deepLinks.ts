const deepLinkBase = "fitician://app";

type MemberDeepLinkResource = "cycles" | "exercises" | "plans";

export function normalizeMemberDeepLinkPath(path: string): string {
  let parsed: URL;
  try {
    parsed = new URL(path, deepLinkBase);
  } catch {
    return path;
  }

  const segments = parsed.pathname
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => decodeSegment(segment));
  const routeSegments = parsed.hostname === "member"
    ? ["member", ...segments]
    : segments;
  const normalizedSegments = routeSegments[0] === "link"
    ? routeSegments.slice(1)
    : routeSegments;

  if (normalizedSegments[0] !== "member") return path;
  const resource = normalizedSegments[1] as MemberDeepLinkResource | undefined;
  const identifier = normalizedSegments[2];
  if (
    identifier === undefined
    || normalizedSegments.length !== 3
    || (resource !== "cycles" && resource !== "exercises" && resource !== "plans")
  ) {
    return path;
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
