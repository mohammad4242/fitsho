import { access, readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "app");

async function routeExists(route: string): Promise<boolean> {
  try {
    await access(resolve(appRoot, route));
    return true;
  } catch {
    return false;
  }
}

async function routeFiles(directory: string): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const entryPath = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await routeFiles(entryPath)));
    } else if (entry.name.endsWith(".tsx")) {
      files.push(entryPath);
    }
  }
  return files;
}

it("defines the public, auth, onboarding, member, coach, and physician route groups", async () => {
  const requiredRoutes = [
    "(public)/_layout.tsx",
    "(public)/index.tsx",
    "(auth)/_layout.tsx",
    "(auth)/auth/sign-in.tsx",
    "(auth)/auth/register.tsx",
    "(auth)/auth/phone-otp.tsx",
    "(auth)/auth/forgot-password.tsx",
    "(auth)/auth/reset-password.tsx",
    "(auth)/auth/verify-email.tsx",
    "(onboarding)/_layout.tsx",
    "(onboarding)/onboarding/index.tsx",
    "(member)/_layout.tsx",
    "(member)/member/_layout.tsx",
    "(member)/member/(tabs)/_layout.tsx",
    "(member)/member/(tabs)/index.tsx",
    "(member)/member/(tabs)/workouts.tsx",
    "(member)/member/(tabs)/nutrition.tsx",
    "(member)/member/(tabs)/profile.tsx",
    "(member)/member/exercises/index.tsx",
    "(member)/member/exercises/[slug].tsx",
    "(coach)/_layout.tsx",
    "(coach)/coach/index.tsx",
    "(physician)/_layout.tsx",
    "(physician)/physician/index.tsx",
  ];

  await expect(Promise.all(requiredRoutes.map(routeExists))).resolves.toEqual(
    requiredRoutes.map(() => true),
  );
});

it("uses native stack and tab navigators without an admin route", async () => {
  const stackLayouts = [
    "(public)/_layout.tsx",
    "(auth)/_layout.tsx",
    "(onboarding)/_layout.tsx",
    "(member)/_layout.tsx",
    "(coach)/_layout.tsx",
    "(physician)/_layout.tsx",
  ];
  for (const layout of stackLayouts) {
    await expect(readFile(resolve(appRoot, layout), "utf8")).resolves.toMatch(/<Stack/);
  }
  await expect(
    readFile(resolve(appRoot, "(member)/member/(tabs)/_layout.tsx"), "utf8"),
  ).resolves.toMatch(/<Tabs/);

  const files = await routeFiles(appRoot);
  expect(files.some((file) => file.includes("/admin/"))).toBe(false);
});

it("places route guards at group boundaries and hides capability tabs", async () => {
  const guardedLayouts: Record<string, string> = {
    "(auth)/_layout.tsx": 'kind="auth"',
    "(coach)/_layout.tsx": 'kind="coach"',
    "(member)/_layout.tsx": 'kind="member"',
    "(onboarding)/_layout.tsx": 'kind="onboarding"',
    "(physician)/_layout.tsx": 'kind="physician"',
    "(public)/_layout.tsx": 'kind="public"',
  };
  for (const [layout, marker] of Object.entries(guardedLayouts)) {
    await expect(readFile(resolve(appRoot, layout), "utf8")).resolves.toContain(marker);
  }
  await expect(
    readFile(resolve(appRoot, "(member)/member/(tabs)/_layout.tsx"), "utf8"),
  ).resolves.toMatch(/href: .*null/);
  await expect(readFile(resolve(appRoot, "_layout.tsx"), "utf8")).resolves.toContain(
    "MobileRouteStateProvider",
  );
  await expect(readFile(resolve(appRoot, "_layout.tsx"), "utf8")).resolves.toContain(
    "AndroidBackBehaviorProvider",
  );
});

it("uses the native onboarding flow instead of a route placeholder", async () => {
  await expect(
    readFile(resolve(appRoot, "(onboarding)/onboarding/index.tsx"), "utf8"),
  ).resolves.toMatch(/OnboardingScreen/);
  await expect(
    readFile(resolve(appRoot, "(onboarding)/onboarding/index.tsx"), "utf8"),
  ).resolves.toMatch(/onboarding\/OnboardingScreen/);
});

it("uses the native profile editor inside the member profile tab", async () => {
  await expect(
    readFile(resolve(appRoot, "(member)/member/(tabs)/profile.tsx"), "utf8"),
  ).resolves.toMatch(/ProfileScreen/);
  await expect(
    readFile(resolve(appRoot, "(member)/member/(tabs)/profile.tsx"), "utf8"),
  ).resolves.not.toMatch(/RouteEntryScreen/);
});

it("keeps the exercise library inside the completed member training boundary", async () => {
  await expect(
    readFile(resolve(appRoot, "(member)/member/exercises/index.tsx"), "utf8"),
  ).resolves.toMatch(/requiredCapability="training"/);
  await expect(
    readFile(resolve(appRoot, "(member)/member/exercises/[slug].tsx"), "utf8"),
  ).resolves.toMatch(/requiredCapability="training"/);
});
