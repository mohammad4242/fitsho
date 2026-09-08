const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(access[_-]?token|refresh[_-]?token|id[_-]?token|device[_-]?token|fcm[_-]?token|token|authorization|cookie|password|secret|api[_-]?key|email|phone|user[_-]?id|image|photo|body|lab|laboratory|medical|diagnos|symptom|medication|supplement|document|filename|uri|address|latitude|longitude|date[_-]?of[_-]?birth|dob|full[_-]?name|display[_-]?name)/iu;
const SAFE_CORRELATION_ID = /^[A-Za-z0-9._:-]{1,128}$/u;
const SAFE_CONTEXT_KEY = /^(app_version|attempt|build_number|cache_hit|correlation_id|duration_ms|error_code|error_type|event|http_status|is_online|method|operation|outcome|permission_status|platform|release|retryable|route_kind|screen|status|success|type)$/u;
const SAFE_DIAGNOSTIC_KEY = /^(api_base_url|environment|error_type|is_online|message|network_type|operation|role|route_kind|status|target)$/u;

declare const __DEV__: boolean | undefined;

export const CORRELATION_ID_HEADER = "X-Correlation-ID";

export type MobileTelemetryLevel = "info" | "warning" | "error";

export type MobileTelemetryEvent =
  | "native_request_completed"
  | "native_request_failed";

export type MobileTelemetryContext = Readonly<Record<string, unknown>>;

export type MobileDiagnosticEvent =
  | "runtime_configuration"
  | "emulator_only_api_target"
  | "auth_restore_failed"
  | "profile_bootstrap_failed"
  | "specialist_access_failed"
  | "connectivity_changed"
  | "routing_bootstrap_failed";

export interface SentryCompatibleAdapter {
  captureException(error: Error, context: MobileTelemetryContext): void;
  captureMessage(
    message: string,
    level: MobileTelemetryLevel,
    context: MobileTelemetryContext,
  ): void;
}

export interface MobileLogger {
  captureException(
    event: MobileTelemetryEvent,
    error: unknown,
    context?: MobileTelemetryContext,
  ): void;
  captureMessage(
    event: MobileTelemetryEvent,
    level: MobileTelemetryLevel,
    context?: MobileTelemetryContext,
  ): void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function redactValue(value: unknown, sensitive = false): unknown {
  if (sensitive) {
    return REDACTED;
  }
  if (typeof value === "string") {
    return redactLogMessage(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => redactValue(item));
  }
  if (isRecord(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, redactValue(item, SENSITIVE_KEY.test(key))]),
    );
  }
  return value;
}

export function redactLogData(value: unknown): unknown {
  return redactValue(value);
}

export function redactLogMessage(message: string): string {
  return message
    .replace(/\bBearer\s+\S+/giu, `Bearer ${REDACTED}`)
    .replace(/\bCookie\s*=\s*\S+/giu, `Cookie=${REDACTED}`)
    .replace(/\b(?:https?|file|content):\/\/\S+/giu, REDACTED)
    .replace(
      /\b(email|phone(?:_number)?|user[_-]?id|access[_-]?token|refresh[_-]?token|id[_-]?token|device[_-]?token|fcm[_-]?token|token|password|secret|api[_-]?key)\s*=\s*\S+/giu,
      (_match, key: string) => `${key}=${REDACTED}`,
    )
    .replace(/[\w.!#$%&'*+/=?^`{|}~-]+@[\w](?:[\w-]{0,61}[\w])?(?:\.[\w](?:[\w-]{0,61}[\w])?)+/gu, REDACTED)
    .replace(/\b(?:\+?\d[\d\s().-]{7,}\d)\b/gu, REDACTED)
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/gu, REDACTED);
}

export function createCorrelationId(): string {
  const randomUUID = globalThis.crypto?.randomUUID;
  if (typeof randomUUID === "function") {
    return randomUUID.call(globalThis.crypto);
  }
  return `fitician-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function safeCorrelationId(value: unknown): string | null {
  return typeof value === "string" && SAFE_CORRELATION_ID.test(value) ? value : null;
}

function safeContextValue(value: unknown): string | number | boolean | null {
  if (typeof value === "string") return redactLogMessage(value);
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean" || value === null) return value;
  return null;
}

function safeDiagnosticUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
    const port = parsed.port.length > 0 ? `:${parsed.port}` : "";
    return `${parsed.protocol}//${parsed.hostname}${port}${parsed.pathname.replace(/\/$/u, "")}`;
  } catch {
    return null;
  }
}

function diagnosticContext(
  context: MobileTelemetryContext,
): Record<string, string | number | boolean | null> {
  const sanitized: Record<string, string | number | boolean | null> = {};
  for (const [key, value] of Object.entries(context)) {
    if (!SAFE_DIAGNOSTIC_KEY.test(key)) continue;
    if (key === "api_base_url") {
      const url = safeDiagnosticUrl(value);
      if (url !== null) sanitized[key] = url;
      continue;
    }
    const safeValue = safeContextValue(value);
    if (safeValue !== null || value === null) sanitized[key] = safeValue;
  }
  return sanitized;
}

function developmentDiagnosticsEnabled(): boolean {
  return typeof __DEV__ !== "undefined" && __DEV__ === true;
}

export function logDevelopmentDiagnostic(
  event: MobileDiagnosticEvent,
  level: MobileTelemetryLevel,
  context: MobileTelemetryContext = {},
  enabled = developmentDiagnosticsEnabled(),
): void {
  if (!enabled) return;
  const safeContext = diagnosticContext(context);
  const message = `[Fitician][${event}]`;
  if (level === "error") {
    console.error(message, safeContext);
  } else if (level === "warning") {
    console.warn(message, safeContext);
  } else {
    console.info(message, safeContext);
  }
}

function telemetryContext(
  context: MobileTelemetryContext,
  correlationIdFactory: () => string,
): Record<string, string | number | boolean | null> {
  const sanitized: Record<string, string | number | boolean | null> = {};
  for (const [key, value] of Object.entries(context)) {
    if (!SAFE_CONTEXT_KEY.test(key)) continue;
    const safeValue = safeContextValue(value);
    if (safeValue !== null || value === null) sanitized[key] = safeValue;
  }
  sanitized.correlation_id = safeCorrelationId(sanitized.correlation_id)
    ?? correlationIdFactory();
  return sanitized;
}

function safeErrorType(error: unknown): string {
  if (error instanceof Error && error.name.length > 0 && /^[A-Za-z0-9_$.-]+$/u.test(error.name)) {
    return error.name;
  }
  return typeof error;
}

export class MobileTelemetryLogger implements MobileLogger {
  constructor(
    private adapter: SentryCompatibleAdapter | null = null,
    private readonly correlationIdFactory: () => string = createCorrelationId,
  ) {}

  setAdapter(adapter: SentryCompatibleAdapter | null): void {
    this.adapter = adapter;
  }

  captureMessage(
    event: MobileTelemetryEvent,
    level: MobileTelemetryLevel,
    context: MobileTelemetryContext = {},
  ): void {
    const adapter = this.adapter;
    if (adapter === null) return;
    const safeContext = telemetryContext({ ...context, event }, this.correlationIdFactory);
    try {
      adapter.captureMessage(event, level, safeContext);
    } catch {
      // Telemetry failures must never interrupt the app.
    }
  }

  captureException(
    event: MobileTelemetryEvent,
    error: unknown,
    context: MobileTelemetryContext = {},
  ): void {
    const adapter = this.adapter;
    if (adapter === null) return;
    const safeContext = telemetryContext(
      { ...context, error_type: safeErrorType(error), event },
      this.correlationIdFactory,
    );
    try {
      adapter.captureException(
        new Error("Fitician mobile telemetry exception"),
        safeContext,
      );
    } catch {
      // Telemetry failures must never interrupt the app.
    }
  }
}

export const mobileLogger = new MobileTelemetryLogger();

export function configureMobileTelemetry(adapter: SentryCompatibleAdapter | null): void {
  mobileLogger.setAdapter(adapter);
}
