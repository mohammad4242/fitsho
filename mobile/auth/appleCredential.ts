export interface AppleFullNameLike {
  readonly familyName?: string | null;
  readonly givenName?: string | null;
}

export interface AppleCredentialLike {
  readonly email?: string | null;
  readonly fullName?: AppleFullNameLike | null;
  readonly identityToken?: string | null;
}

export interface AppleAuthCredential {
  readonly email: string | null;
  readonly fullName: string | null;
  readonly identityToken: string;
  readonly nonce: string;
}

export class AppleSignInFlowError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AppleSignInFlowError";
  }
}

function optionalText(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized === undefined || normalized === "" ? null : normalized;
}

export function appleCredentialFromResult(
  result: AppleCredentialLike,
  nonce: string,
): AppleAuthCredential | null {
  const identityToken = optionalText(result.identityToken);
  if (identityToken === null) return null;
  const givenName = optionalText(result.fullName?.givenName);
  const familyName = optionalText(result.fullName?.familyName);
  return {
    email: optionalText(result.email),
    fullName:
      [givenName, familyName].filter((part): part is string => part !== null).join(" ") || null,
    identityToken,
    nonce,
  };
}

export function appleResultMessage(error: unknown): string {
  if (
    typeof error === "object"
    && error !== null
    && "code" in error
    && error.code === "ERR_REQUEST_CANCELED"
  ) {
    return "ورود با اپل لغو شد.";
  }
  return "ورود با اپل انجام نشد. دوباره تلاش کنید.";
}
