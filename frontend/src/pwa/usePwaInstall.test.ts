import { describe, expect, it } from "vitest";

import { getPwaInstallState } from "./usePwaInstall";

describe("getPwaInstallState", () => {
  it("uses iOS instructions outside standalone mode", () => {
    expect(getPwaInstallState({
      userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
      standalone: false,
      displayModeStandalone: false,
    })).toBe("ios-instructions");
  });

  it("does not offer installation after the PWA is installed", () => {
    expect(getPwaInstallState({
      userAgent: "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)",
      standalone: true,
      displayModeStandalone: true,
    })).toBe("installed");
  });

  it("keeps Chromium eligible for its real install prompt", () => {
    expect(getPwaInstallState({
      userAgent: "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36",
      standalone: false,
      displayModeStandalone: false,
    })).toBe("chromium");
  });

  it("recognizes iPadOS desktop-mode Safari", () => {
    expect(getPwaInstallState({
      userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
      platform: "MacIntel",
      maxTouchPoints: 5,
      standalone: false,
      displayModeStandalone: false,
    })).toBe("ios-instructions");
  });
});
