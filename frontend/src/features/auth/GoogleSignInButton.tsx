import { useEffect, useRef } from "react";

type GoogleCredentialResponse = {
  credential?: string;
};

type GoogleAccountsId = {
  initialize: (options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
  }) => void;
  renderButton: (
    parent: HTMLElement,
    options: {
      theme: "outline";
      size: "large";
      shape: "rectangular";
      width: number;
      locale: string;
    },
  ) => void;
};

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
  }
}

const GOOGLE_SCRIPT_ID = "google-identity-services";
const GOOGLE_SCRIPT_URL = "https://accounts.google.com/gsi/client";

export function GoogleBrandIcon({
  className,
  decorative = false,
}: {
  className?: string;
  decorative?: boolean;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "Google"}
      aria-hidden={decorative || undefined}
    >
      <path
        fill="#4285F4"
        d="M21.35 12.27c0-.78-.07-1.54-.23-2.27H12v4.3h5.23a4.5 4.5 0 0 1-1.94 2.96v2.46h3.14c1.84-1.69 2.92-4.18 2.92-7.45Z"
      />
      <path
        fill="#34A853"
        d="M12 21.5c2.63 0 4.84-.87 6.45-2.35l-3.14-2.46c-.87.58-1.98.93-3.31.93-2.54 0-4.69-1.72-5.46-4.04H3.3v2.54A9.74 9.74 0 0 0 12 21.5Z"
      />
      <path
        fill="#FBBC05"
        d="M6.54 13.58A5.86 5.86 0 0 1 6.23 12c0-.55.11-1.08.31-1.58V7.88H3.3A9.5 9.5 0 0 0 2.5 12c0 1.49.36 2.9.8 4.12l3.24-2.54Z"
      />
      <path
        fill="#EA4335"
        d="M12 6.38c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.44 14.63 2.5 12 2.5a9.74 9.74 0 0 0-8.7 5.38l3.24 2.54C7.31 8.1 9.46 6.38 12 6.38Z"
      />
    </svg>
  );
}

function loadGoogleIdentityServices(): Promise<void> {
  if (window.google) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("Google script failed")), {
        once: true,
      });
      return;
    }
    const script = document.createElement("script");
    script.id = GOOGLE_SCRIPT_ID;
    script.src = GOOGLE_SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve(), { once: true });
    script.addEventListener("error", () => reject(new Error("Google script failed")), {
      once: true,
    });
    document.head.append(script);
  });
}

export function GoogleSignInButton({
  onCredential,
  onError,
  disabled,
}: {
  onCredential: (credential: string) => void;
  onError: () => void;
  disabled: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const onCredentialRef = useRef(onCredential);
  const onErrorRef = useRef(onError);
  onCredentialRef.current = onCredential;
  onErrorRef.current = onError;
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();

  useEffect(() => {
    if (!clientId) return;
    let active = true;
    void loadGoogleIdentityServices()
      .then(() => {
        if (!active || !window.google || !container.current) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response.credential) onCredentialRef.current(response.credential);
            else onErrorRef.current();
          },
        });
        const width = Math.min(400, Math.max(240, container.current.clientWidth || 320));
        window.google.accounts.id.renderButton(container.current, {
          theme: "outline",
          size: "large",
          shape: "rectangular",
          width,
          locale: document.documentElement.lang || "fa",
        });
      })
      .catch(() => {
        if (active) onErrorRef.current();
      });
    return () => {
      active = false;
    };
  }, [clientId]);

  if (!clientId) {
    return (
      <button
        className="google-sign-in-fallback"
        type="button"
        onClick={() => onErrorRef.current()}
        disabled={disabled}
      >
        <GoogleBrandIcon className="google-sign-in-fallback__icon" decorative />
        <span>Google</span>
      </button>
    );
  }
  return (
    <div
      ref={container}
      className="google-sign-in-slot"
      aria-busy={disabled}
      data-disabled={disabled || undefined}
    />
  );
}
