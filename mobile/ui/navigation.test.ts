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

it("defines the public, auth, onboarding, account, member, coach, and physician route groups", async () => {
  const requiredRoutes = [
    "(public)/_layout.tsx",
    "(public)/index.tsx",
    "(public)/public-onboarding.tsx",
    "(auth)/_layout.tsx",
    "(auth)/auth/sign-in.tsx",
    "(auth)/auth/register.tsx",
    "(auth)/auth/phone-otp.tsx",
    "(auth)/auth/forgot-password.tsx",
    "(auth)/auth/reset-password.tsx",
    "(auth)/auth/verify-email.tsx",
    "(onboarding)/_layout.tsx",
    "(onboarding)/onboarding/index.tsx",
    "(account)/_layout.tsx",
    "(account)/account-deletion.tsx",
    "(member)/_layout.tsx",
    "(member)/member/_layout.tsx",
    "(member)/member/(tabs)/_layout.tsx",
    "(member)/member/(tabs)/index.tsx",
    "(member)/member/(tabs)/workouts.tsx",
    "(member)/member/(tabs)/nutrition.tsx",
    "(member)/member/(tabs)/body-analysis.tsx",
    "(member)/member/(tabs)/more.tsx",
    "(member)/member/nutrition-tracking.tsx",
    "(member)/member/food-catalogue.tsx",
    "(member)/member/meal-catalogue.tsx",
    "(member)/member/profile.tsx",
    "(member)/member/body-analysis.tsx",
    "(member)/member/body-analysis-history.tsx",
    "(member)/member/body-analysis-result/[sessionId].tsx",
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
    "(account)/_layout.tsx",
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
    "(account)/_layout.tsx": 'kind="account"',
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

it("uses the custom safe-area-aware member tab navigation", async () => {
  const route = resolve(appRoot, "(member)/member/(tabs)/_layout.tsx");
  const source = await readFile(route, "utf8");
  expect(source).toContain("MemberBottomTabBar");
  expect(source).toContain("tabBar");
  expect(source).toContain("useSafeAreaInsets");
  expect(source).toContain("safeAreaInsets");
  expect(source).not.toContain("surfaceTranslucent");
});

it("defines web-equivalent member bottom-bar icons and styling", async () => {
  const component = resolve(dirname(appRoot), "ui/navigation/MemberBottomTabBar.tsx");
  const source = await readFile(component, "utf8");

  expect(source).toContain('home:');
  expect(source).toContain('dumbbell:');
  expect(source).toContain('nutrition:');
  expect(source).toContain('progress:');
  expect(source).toContain('more:');
  expect(source).toContain('d="m3 10 9-7 9 7"');
  expect(source).toContain('d="M7 8v8M4.5 9.5v5M2.5 11v2');
  expect(source).toContain('d="M12 21c5-3 7-7 7-11');
  expect(source).toContain('d="M4 19V5M4 19h16"');
  expect(source).toContain('<Circle cx="5" cy="12" r="1" />');
  expect(source).toMatch(/index: "home"/);
  expect(source).toMatch(/workouts: "dumbbell"/);
  expect(source).toMatch(/nutrition: "nutrition"/);
  expect(source).toMatch(/"body-analysis": "progress"/);
  expect(source).toMatch(/more: "more"/);
  expect(source).toContain("aquaAtmosphere");
  expect(source).toContain("activeIndicator");
  expect(source).toContain("insets.bottom");
  expect(source).toContain("paddingBottom");
  expect(source).toContain("NAVIGATION_CONTENT_HEIGHT");
  expect(source).toContain('backgroundColor: fiticianTokens.colors.canvas');
  expect(source).toContain('borderTopWidth: 1');
  expect(source).toContain('display !== "none"');
  expect(source).toContain('type: "tabPress"');
  expect(source).toContain('type: "tabLongPress"');
  expect(source).toContain('navigation.navigate(route.name, route.params)');
  expect(source).toContain('accessibilityRole="button"');
  expect(source).toContain('accessibilityState={{ selected: focused }}');
  expect(source).not.toContain("surfaceTranslucent");
});

it("keeps account deletion available to any signed-in role without admin routes", async () => {
  await expect(readFile(resolve(appRoot, "(account)/account-deletion.tsx"), "utf8"))
    .resolves.toMatch(/AccountDeletionScreen/);
  await expect(readFile(resolve(appRoot, "(account)/_layout.tsx"), "utf8"))
    .resolves.not.toMatch(/AdminRoute|admin/);
});

it("uses the native onboarding flow instead of a route placeholder", async () => {
  await expect(
    readFile(resolve(appRoot, "(onboarding)/onboarding/index.tsx"), "utf8"),
  ).resolves.toMatch(/OnboardingScreen/);
  await expect(
    readFile(resolve(appRoot, "(onboarding)/onboarding/index.tsx"), "utf8"),
  ).resolves.toMatch(/onboarding\/OnboardingScreen/);
});

it("keeps public onboarding native and connected to the account handoff", async () => {
  await expect(
    readFile(resolve(appRoot, "(public)/public-onboarding.tsx"), "utf8"),
  ).resolves.toMatch(/PublicOnboardingScreen/);
  await expect(readFile(resolve(appRoot, "(public)/index.tsx"), "utf8"))
    .resolves.toContain("/public-onboarding");
  await expect(readFile(resolve(dirname(appRoot), "onboarding/PublicOnboardingScreen.tsx"), "utf8"))
    .resolves.toContain("PUBLIC_ONBOARDING_SOURCE");
  await expect(readFile(resolve(dirname(appRoot), "onboarding/OnboardingScreen.tsx"), "utf8"))
    .resolves.toContain("hydratePublicOnboardingState");
});

it("keeps the native profile editor in the member stack and removes its tab route", async () => {
  await expect(routeExists("(member)/member/(tabs)/profile.tsx")).resolves.toBe(false);
  await expect(
    readFile(resolve(appRoot, "(member)/member/profile.tsx"), "utf8"),
  ).resolves.toMatch(/ProfileScreen/);
  await expect(
    readFile(resolve(appRoot, "(member)/member/profile.tsx"), "utf8"),
  ).resolves.not.toMatch(/RouteEntryScreen/);
});

it("keeps Body Progress capability-aware and More as the fifth member tab", async () => {
  const source = await readFile(
    resolve(appRoot, "(member)/member/(tabs)/_layout.tsx"),
    "utf8",
  );
  const tabNames = Array.from(source.matchAll(/<Tabs\.Screen\s+name="([^"]+)"/g), (match) => match[1]);
  expect(tabNames).toEqual(["index", "workouts", "nutrition", "body-analysis", "more"]);
  expect(source).toContain('tabBarLabel: "امروز"');
  expect(source).toContain('tabBarLabel: "تمرین"');
  expect(source).toContain('tabBarLabel: "تغذیه"');
  expect(source).toContain('tabBarLabel: "Body Analysis"');
  expect(source).toContain('tabBarLabel: "بیشتر"');
  expect(source).toContain('name="body-analysis"');
  expect(source).toMatch(/name="workouts"[\s\S]*?href: showTraining \? undefined : null/);
  expect(source).toMatch(/name="nutrition"[\s\S]*?href: showNutrition \? undefined : null/);
  expect(source).toMatch(/name="body-analysis"[\s\S]*?href: showTraining \? undefined : null/);
  expect(source).not.toContain('name="profile"');
  await expect(
    readFile(resolve(appRoot, "(member)/member/(tabs)/more.tsx"), "utf8"),
  ).resolves.toMatch(/MoreScreen/);
});

it("opens Body Progress from the tab without replacing the capture wizard", async () => {
  const tabRoute = resolve(appRoot, "(member)/member/(tabs)/body-analysis.tsx");
  const tabSource = await readFile(tabRoute, "utf8");
  expect(tabSource).toContain("BodyAnalysisHistoryScreen");
  expect(tabSource).toContain('requiredCapability="training"');
  expect(tabSource).not.toContain("BodyAnalysisWizard");

  const captureRoute = resolve(appRoot, "(member)/member/body-analysis.tsx");
  const captureSource = await readFile(captureRoute, "utf8");
  expect(captureSource).toContain("BodyAnalysisWizard");
  expect(captureSource).not.toContain("BodyAnalysisHistoryScreen");
});

it("uses the data-driven member home instead of the route-entry placeholder", async () => {
  const route = resolve(appRoot, "(member)/member/(tabs)/index.tsx");
  await expect(readFile(route, "utf8")).resolves.toMatch(/MemberHomeScreen/);
  await expect(readFile(route, "utf8")).resolves.not.toMatch(/RouteEntryScreen/);
});

it("uses the native body-analysis wizard inside the member boundary", async () => {
  const route = resolve(appRoot, "(member)/member/body-analysis.tsx");
  await expect(readFile(route, "utf8")).resolves.toMatch(/BodyAnalysisWizard/);
  await expect(readFile(route, "utf8")).resolves.toMatch(/member/);
});

it("keeps the exercise library inside the completed member training boundary", async () => {
  await expect(
    readFile(resolve(appRoot, "(member)/member/exercises/index.tsx"), "utf8"),
  ).resolves.toMatch(/requiredCapability="training"/);
  await expect(
    readFile(resolve(appRoot, "(member)/member/exercises/[slug].tsx"), "utf8"),
  ).resolves.toMatch(/requiredCapability="training"/);
});

it("uses the native workout plan screen inside the completed member training boundary", async () => {
  const route = resolve(appRoot, "(member)/member/(tabs)/workouts.tsx");
  await expect(readFile(route, "utf8")).resolves.toMatch(/WorkoutPlansScreen/);
  await expect(readFile(route, "utf8")).resolves.not.toMatch(/RouteEntryScreen/);
  await expect(readFile(route, "utf8")).resolves.toMatch(/requiredCapability="training"/);
});

it("uses the native nutrition foundation inside the completed member nutrition boundary", async () => {
  const route = resolve(appRoot, "(member)/member/(tabs)/nutrition.tsx");
  await expect(readFile(route, "utf8")).resolves.toMatch(/NutritionFoundationScreen/);
  await expect(readFile(route, "utf8")).resolves.not.toMatch(/RouteEntryScreen/);
  await expect(readFile(route, "utf8")).resolves.toMatch(/requiredCapability="nutrition"/);
});

it("keeps food tracking as a focused native nutrition route", async () => {
  const route = resolve(appRoot, "(member)/member/nutrition-tracking.tsx");
  await expect(readFile(route, "utf8")).resolves.toMatch(/NutritionTrackingSection/);
  await expect(readFile(route, "utf8")).resolves.toMatch(/requiredCapability="nutrition"/);
});

it("keeps weekly nutrition plans inside the native nutrition surface", async () => {
  const screen = resolve(dirname(appRoot), "nutrition/NutritionFoundationScreen.tsx");
  await expect(readFile(screen, "utf8")).resolves.toMatch(/NutritionPlanSection/);
});

it("keeps member catalogue browsing and shopping prices inside approved nutrition surfaces", async () => {
  const foundation = resolve(dirname(appRoot), "nutrition/NutritionFoundationScreen.tsx");
  const plan = resolve(dirname(appRoot), "nutrition/NutritionPlanSection.tsx");
  const catalogue = resolve(dirname(appRoot), "nutrition/NutritionCatalogueSection.tsx");
  const catalogueRoute = resolve(appRoot, "(member)/member/food-catalogue.tsx");

  await expect(readFile(foundation, "utf8")).resolves.not.toMatch(/<NutritionCatalogueSection\b/);
  await expect(readFile(plan, "utf8")).resolves.toMatch(/NutritionShoppingList/);
  await expect(readFile(catalogue, "utf8")).resolves.not.toMatch(/\/admin\//);
  await expect(readFile(catalogueRoute, "utf8")).resolves.toMatch(/NutritionCatalogueSection/);
});
