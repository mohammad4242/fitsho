function configuredBackendOrigin(apiBaseUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(apiBaseUrl);
  } catch {
    throw new Error("The configured backend URL is invalid");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("The configured backend URL must use HTTP(S)");
  }
  return parsed.origin;
}

export function resolveBackendResourceUrl(path: string, apiBaseUrl: string): string {
  const normalizedPath = path.trim();
  if (normalizedPath.length === 0) {
    throw new Error("A backend resource path is required");
  }

  const backendOrigin = configuredBackendOrigin(apiBaseUrl);
  if (/^https?:\/\//i.test(normalizedPath)) {
    const absoluteUrl = new URL(normalizedPath);
    if (absoluteUrl.origin !== backendOrigin) {
      throw new Error("Backend resource URL must use the configured backend origin");
    }
    return absoluteUrl.toString();
  }

  if (normalizedPath.startsWith("//") || /^[a-z][a-z\d+.-]*:/i.test(normalizedPath)) {
    throw new Error("Backend resource URL must use the configured backend origin");
  }

  return `${apiBaseUrl.replace(/\/+$/u, "")}/${normalizedPath.replace(/^\/+/, "")}`;
}
