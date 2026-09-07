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
    "(onboarding)/_layout.tsx",
    "(onboarding)/onboarding/index.tsx",
    "(member)/_layout.tsx",
    "(member)/member/_layout.tsx",
    "(member)/member/(tabs)/_layout.tsx",
    "(member)/member/(tabs)/index.tsx",
    "(member)/member/(tabs)/workouts.tsx",
    "(member)/member/(tabs)/nutrition.tsx",
    "(member)/member/(tabs)/profile.tsx",
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
