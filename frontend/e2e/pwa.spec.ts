import { expect, test } from "@playwright/test";

test("serves a valid Fitician manifest and icons", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBe(true);
  const manifest = await response.json() as {
    name: string;
    short_name: string;
    description: string;
    lang: string;
    dir: string;
    start_url: string;
    scope: string;
    display: string;
    background_color: string;
    theme_color: string;
    icons: Array<{ src: string; sizes: string; type: string; purpose?: string }>;
  };
  expect(manifest.name).toContain("Fitician");
  expect(manifest.short_name).toBe("Fitician");
  expect(manifest.description).toContain("فیتیشن");
  expect(manifest.lang).toBe("fa");
  expect(manifest.dir).toBe("rtl");
  expect(manifest.start_url).toBe("/");
  expect(manifest.scope).toBe("/");
  expect(manifest.display).toBe("standalone");
  expect(manifest.background_color).toBe("#020607");
  expect(manifest.theme_color).toBe("#020607");
  expect(manifest.icons.map((icon) => icon.src)).toEqual(expect.arrayContaining([
    "/pwa/icon-192.png",
    "/pwa/icon-512.png",
    "/pwa/icon-maskable-512.png",
  ]));
  for (const icon of ["/pwa/icon-192.png", "/pwa/icon-512.png", "/pwa/icon-maskable-512.png", "/pwa/apple-touch-icon.png"]) {
    const iconResponse = await request.get(icon);
    expect(iconResponse.ok(), icon).toBe(true);
    expect(iconResponse.headers()["content-type"]).toContain("image/png");
  }
});

test("registers the production service worker without critical console errors", async ({ page, browserName }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/api/**", (route) => route.fulfill({
    status: 401,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Not authenticated in the browser fixture" }),
  }));
  await page.goto("/", { waitUntil: "networkidle" });
  if (browserName === "chromium") {
    await expect.poll(() => page.evaluate(async () => (
      "serviceWorker" in navigator
        ? (await navigator.serviceWorker.getRegistrations()).some((registration) => registration.scope.endsWith("/"))
        : false
    )), { timeout: 15_000 }).toBe(true);
  }
  expect(errors.filter((message) => (
    !message.includes("favicon")
    && !message.includes("status of 401 (Unauthorized)")
  ))).toEqual([]);
});

test("production shell does not precache private or large public data", async ({ request }) => {
  const serviceWorker = await (await request.get("/sw.js")).text();
  expect(serviceWorker).not.toContain("fitsho_1000_profiles_audit_report");
  expect(serviceWorker).not.toContain("workout_engine_11_profiles");
  expect(serviceWorker).not.toContain("image&videos/");
  expect(serviceWorker).not.toContain("mediapipe/");
  expect(serviceWorker).not.toContain("/media/");
  expect(serviceWorker).not.toContain("/api/");
});

test("production preview serves SPA deep links", async ({ request }) => {
  for (const path of ["/workout-plan", "/body-progress", "/nutrition-tracking"]) {
    const response = await request.get(path);
    expect(response.status(), path).toBe(200);
    expect(await response.text(), path).toContain("Fitician");
  }
});
