const LOCAL_ORIGIN = "https://fitsho.local";

export function safeReturnTo(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "" || value.includes("\\")) {
    return "/dashboard";
  }
  if (!value.startsWith("/") || value.startsWith("//")) {
    return "/dashboard";
  }
  try {
    const url = new URL(value, LOCAL_ORIGIN);
    if (url.origin !== LOCAL_ORIGIN) return "/dashboard";
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return "/dashboard";
  }
}

export function authPath(path: "/login" | "/register", returnTo: string): string {
  return `${path}?returnTo=${encodeURIComponent(safeReturnTo(returnTo))}`;
}
