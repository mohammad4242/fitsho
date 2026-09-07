const ENVIRONMENT_NAMES = new Set(["development", "preview", "production"]);
const APP_LINK_PLACEHOLDER = "app.fitician.example";

export function parseEnvFile(contents) {
  const values = {};
  for (const [lineNumber, rawLine] of contents.split(/\r?\n/).entries()) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator <= 0) throw new Error(`Invalid environment entry on line ${lineNumber + 1}`);
    const key = line.slice(0, separator).trim();
    const rawValue = line.slice(separator + 1).trim();
    if (!/^[A-Z][A-Z0-9_]*$/.test(key)) {
      throw new Error(`Invalid environment key ${key}`);
    }
    if (key in values) throw new Error(`Duplicate environment key ${key}`);
    values[key] = rawValue.replace(/^("|')(.*)\1$/, "$2");
  }
  return values;
}

function validateHostname(value) {
  if (!value || value.includes("://") || value.includes("/") || value.includes("@")) {
    throw new Error("FITICIAN_APP_LINK_HOST must contain only a hostname");
  }
  const parsed = new URL(`https://${value}`);
  if (parsed.hostname !== value || parsed.port || parsed.pathname !== "/") {
    throw new Error("FITICIAN_APP_LINK_HOST must be a valid HTTPS hostname without a port");
  }
}

export function validateEnvironment(expectedVariant, values, options = {}) {
  if (!ENVIRONMENT_NAMES.has(expectedVariant)) {
    throw new Error(`Unsupported environment ${expectedVariant}`);
  }
  if (values.APP_VARIANT !== expectedVariant) {
    throw new Error(`APP_VARIANT must be ${expectedVariant}`);
  }
  const apiUrl = values.EXPO_PUBLIC_API_BASE_URL;
  if (!apiUrl) throw new Error("EXPO_PUBLIC_API_BASE_URL is required");
  const parsedApiUrl = new URL(apiUrl);
  if (!parsedApiUrl.hostname || (expectedVariant !== "development" && parsedApiUrl.protocol !== "https:")) {
    throw new Error("EXPO_PUBLIC_API_BASE_URL must use HTTPS outside development");
  }

  const appLinkHost = values.FITICIAN_APP_LINK_HOST;
  validateHostname(appLinkHost);
  if (expectedVariant === "production" && appLinkHost === APP_LINK_PLACEHOLDER && !options.allowPlaceholder) {
    throw new Error(
      "FITICIAN_APP_LINK_HOST must be set to a verified HTTPS host for production builds",
    );
  }
}
