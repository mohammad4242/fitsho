import { useEffect, useRef, useState } from "react";

export type PwaInstallState = "ios-instructions" | "chromium" | "installed" | "unsupported";

type PwaInstallEnvironment = {
  userAgent: string;
  standalone: boolean;
  displayModeStandalone: boolean;
  platform?: string;
  maxTouchPoints?: number;
};

type BeforeInstallPromptEvent = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

export function getPwaInstallState(environment: PwaInstallEnvironment): PwaInstallState {
  if (environment.standalone || environment.displayModeStandalone) return "installed";
  const isIos = /(iPad|iPhone|iPod)/i.test(environment.userAgent)
    || environment.platform === "MacIntel" && (environment.maxTouchPoints ?? 0) > 1;
  if (isIos) return "ios-instructions";
  if (/(Chrome|Chromium|CriOS|EdgA|SamsungBrowser)/i.test(environment.userAgent)) return "chromium";
  return "unsupported";
}

export function usePwaInstall() {
  const [state, setState] = useState<PwaInstallState>(detectPwaInstallState);
  const [canPrompt, setCanPrompt] = useState(false);
  const deferredPrompt = useRef<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      deferredPrompt.current = event as BeforeInstallPromptEvent;
      setCanPrompt(true);
    };
    const onAppInstalled = () => {
      deferredPrompt.current = null;
      setCanPrompt(false);
      setState("installed");
    };

    window.addEventListener("beforeinstallprompt", onBeforeInstallPrompt);
    window.addEventListener("appinstalled", onAppInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstallPrompt);
      window.removeEventListener("appinstalled", onAppInstalled);
    };
  }, []);

  async function install() {
    const prompt = deferredPrompt.current;
    if (prompt === null) return;
    deferredPrompt.current = null;
    setCanPrompt(false);
    await prompt.prompt();
    const choice = await prompt.userChoice;
    if (choice.outcome === "accepted") setState("installed");
  }

  return { state, canPrompt, install };
}

function detectPwaInstallState(): PwaInstallState {
  if (typeof window === "undefined" || typeof navigator === "undefined") return "unsupported";
  const navigatorWithStandalone = navigator as Navigator & { standalone?: boolean };
  return getPwaInstallState({
    userAgent: navigator.userAgent,
    standalone: navigatorWithStandalone.standalone === true,
    displayModeStandalone: window.matchMedia?.("(display-mode: standalone)").matches === true,
    platform: navigator.platform,
    maxTouchPoints: navigator.maxTouchPoints,
  });
}
