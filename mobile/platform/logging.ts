const REDACTED = "[REDACTED]";
const SENSITIVE_KEY = /(access[_-]?token|refresh[_-]?token|authorization|cookie|password|secret|email|phone|user[_-]?id|image|photo|body|lab|medical|filename|uri)/iu;

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
    .replace(
      /\b(email|phone(?:_number)?|user[_-]?id|access[_-]?token|refresh[_-]?token|password|secret)\s*=\s*\S+/giu,
      (_match, key: string) => `${key}=${REDACTED}`,
    );
}
