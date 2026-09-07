const tokenAuthPaths = new Set(["/auth/reset-password", "/auth/verify-email"]);

export function isTokenAuthPath(pathname: string): boolean {
  return tokenAuthPaths.has(pathname);
}
