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

  if (!clientId) return null;
  return (
    <div
      ref={container}
      className="google-sign-in-slot"
      aria-busy={disabled}
      data-disabled={disabled || undefined}
    />
  );
}
