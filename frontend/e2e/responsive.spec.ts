import { expect, test, type Page } from "@playwright/test";

const viewports = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
  { name: "desktop", width: 1440, height: 900 },
  { name: "narrow-phone", width: 320, height: 568 },
  { name: "wide-phone", width: 430, height: 932 },
  { name: "tablet-edge", width: 768, height: 1024 },
  { name: "desktop-edge", width: 1366, height: 768 },
  { name: "landscape-phone", width: 844, height: 390 },
];

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => (
    document.documentElement.scrollWidth <= window.innerWidth
    && document.body.scrollWidth <= window.innerWidth
  ))).toBe(true);
}

async function mockCompletedMember(page: Page) {
  await page.route("**/api/**", (route) => route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ detail: "Not available in the browser fixture" }),
  }));
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      id: "018f0000-0000-7000-8000-000000000001",
      email: "member@example.com",
      phone_number: null,
      created_at: "2026-07-24T00:00:00Z",
      is_admin: false,
    }),
  }));
  await page.route("**/api/v1/profile/status", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      user_id: "018f0000-0000-7000-8000-000000000001",
      product_mode: "training",
      completion_state: "training_ready",
    }),
  }));
  await page.route("**/api/v1/profile", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      user_id: "018f0000-0000-7000-8000-000000000001",
      display_name: "Fitician member",
      birth_date: "2000-05-14",
      sex: "male",
      height_cm: 178,
      current_weight_kg: 76.5,
      shoulder_circumference_cm: null,
      waist_circumference_cm: null,
      hip_circumference_cm: null,
      fitness_goal: "build_muscle",
      experience_level: "beginner",
      training_days_per_week: 3,
      training_location: "gym",
      home_training_setup: null,
      session_duration_minutes: 60,
      training_cautions: [],
      plan_duration_weeks: 4,
      physical_limitations: null,
      weight_measured_at: "2026-07-27T10:30:00Z",
      circumferences_measured_at: null,
      created_at: "2026-07-27T10:30:00Z",
      updated_at: "2026-07-27T10:30:00Z",
    }),
  }));
}

for (const viewport of viewports) {
  test(`public routes stay within the ${viewport.name} viewport`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const path of ["/", "/get-started", "/login", "/register"]) {
      await page.goto(path, { waitUntil: "networkidle" });
      await expectNoHorizontalOverflow(page);
      await expect(page.locator("body")).toBeVisible();
    }
  });
}

for (const viewport of viewports) {
  test(`member shell uses the ${viewport.name} navigation contract`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await mockCompletedMember(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(page.locator(".app-shell")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    const shell = await page.evaluate(() => {
      const nav = document.querySelector<HTMLElement>(".app-shell__nav");
      const mobileHeader = document.querySelector<HTMLElement>(".authenticated-header__mobile");
      const desktopHeader = document.querySelector<HTMLElement>(".authenticated-header__desktop");
      const style = (element: HTMLElement | null) => element ? getComputedStyle(element).display : "none";
      return {
        nav: style(nav),
        mobileHeader: style(mobileHeader),
        desktopHeader: style(desktopHeader),
        contentBottomPadding: getComputedStyle(document.querySelector<HTMLElement>(".app-shell__content")!).paddingBottom,
      };
    });

    if (viewport.width < 768) {
      expect(shell.nav).toBe("grid");
      expect(shell.mobileHeader).toBe("flex");
      expect(shell.desktopHeader).toBe("none");
      expect(shell.contentBottomPadding).not.toBe("0px");
    } else {
      expect(shell.nav).toBe("flex");
      expect(shell.mobileHeader).toBe("none");
      expect(shell.desktopHeader).toBe("flex");
    }
  });
}

test("the public menu stays contained on a narrow RTL viewport", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator(".landing-menu-button").click();
  const menu = page.locator(".landing-menu");
  await expect(menu).toBeVisible();
  const box = await menu.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(320);
  expect(box!.y + box!.height).toBeLessThanOrEqual(568);
  await expectNoHorizontalOverflow(page);
});

test("the public shell keeps English LTR semantics", async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem("fitsho-language", "en"));
  await page.goto("/login", { waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expectNoHorizontalOverflow(page);
});
