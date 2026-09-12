import { describe, expect, it } from "vitest";

import { pwaManifest, resolveApiProxyTarget } from "../../vite.config";

describe("resolveApiProxyTarget", () => {
  it("keeps the current local backend as the default", () => {
    expect(resolveApiProxyTarget(undefined)).toBe("http://localhost:8001");
  });

  it("uses the host backend supplied to the frontend container", () => {
    expect(resolveApiProxyTarget("http://host.docker.internal:8002")).toBe(
      "http://host.docker.internal:8002",
    );
  });
});

describe("pwaManifest", () => {
  it("uses the Fitician standalone RTL application identity", () => {
    expect(pwaManifest).toMatchObject({
      name: "Fitician | فیتیشن",
      short_name: "Fitician",
      lang: "fa",
      dir: "rtl",
      start_url: "/",
      scope: "/",
      display: "standalone",
      background_color: "#020607",
      theme_color: "#020607",
    });
    expect(pwaManifest.icons).toEqual(expect.arrayContaining([
      expect.objectContaining({ src: "/pwa/icon-192.png", sizes: "192x192" }),
      expect.objectContaining({ src: "/pwa/icon-maskable-512.png", purpose: "maskable" }),
    ]));
  });
});
