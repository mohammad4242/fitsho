import { describe, expect, it } from "vitest";

import { resolveApiProxyTarget } from "../../vite.config";

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
