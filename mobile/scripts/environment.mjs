import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ENVIRONMENT_NAMES = new Set(["development", "preview", "production"]);
const APP_LINK_PLACEHOLDER = "app.fitician.example";
const mobileRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const endpointConfig = JSON.parse(
  readFileSync(resolve(mobileRoot, "config/productionApiEndpoints.json"), "utf8"),
);
const productionApiBaseUrl = `http://${endpointConfig.tailscaleBackendHost}:${endpointConfig.backendPort}`;
const productionFrontendOrigin = `http://${endpointConfig.tailscaleBackendHost}:${endpointConfig.frontendPort}`;

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
  if (expectedVariant === "production" && apiUrl.replace(/\/+$/u, "") !== productionApiBaseUrl) {
    throw new Error(
      `EXPO_PUBLIC_API_BASE_URL must equal the configured Tailscale backend ${productionApiBaseUrl}`,
    );
  }
  if (
    !parsedApiUrl.hostname
    || (expectedVariant !== "development" && expectedVariant !== "production" && parsedApiUrl.protocol !== "https:")
  ) {
    throw new Error("EXPO_PUBLIC_API_BASE_URL must use HTTPS outside development");
  }

  const frontendOrigin = values.EXPO_PUBLIC_FRONTEND_ORIGIN;
  if (!frontendOrigin) throw new Error("EXPO_PUBLIC_FRONTEND_ORIGIN is required");
  const parsedFrontendOrigin = new URL(frontendOrigin);
  if (
    !parsedFrontendOrigin.hostname ||
    parsedFrontendOrigin.pathname !== "/" ||
    parsedFrontendOrigin.search ||
    parsedFrontendOrigin.hash ||
    (
      expectedVariant !== "development"
      && expectedVariant !== "production"
      && parsedFrontendOrigin.protocol !== "https:"
    )
  ) {
    throw new Error("EXPO_PUBLIC_FRONTEND_ORIGIN must use HTTPS outside development");
  }
  if (
    expectedVariant === "production"
    && frontendOrigin.replace(/\/+$/u, "") !== productionFrontendOrigin
  ) {
    throw new Error(
      `EXPO_PUBLIC_FRONTEND_ORIGIN must equal the configured Tailscale origin ${productionFrontendOrigin}`,
    );
  }

  const appLinkHost = values.FITICIAN_APP_LINK_HOST;
  validateHostname(appLinkHost);
  if (expectedVariant === "production" && appLinkHost === APP_LINK_PLACEHOLDER && !options.allowPlaceholder) {
    throw new Error(
      "FITICIAN_APP_LINK_HOST must be set to a verified HTTPS host for production builds",
    );
  }
}
