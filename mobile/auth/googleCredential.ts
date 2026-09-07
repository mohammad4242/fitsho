export interface GoogleAuthResultLike {
  readonly errorCode?: string | null;
  readonly params?: Readonly<Record<string, string>>;
  readonly type: string;
}

export class GoogleSignInFlowError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GoogleSignInFlowError";
  }
}

export function googleCredentialFromResult(result: GoogleAuthResultLike): string | null {
  if (result.type !== "success") {
    return null;
  }
  const credential = result.params?.id_token?.trim();
  return credential === "" || credential === undefined ? null : credential;
}

export function googleResultMessage(result: GoogleAuthResultLike): string {
  return result.type === "cancel"
    ? "ورود با گوگل لغو شد."
    : "ورود با گوگل انجام نشد. دوباره تلاش کنید.";
}
