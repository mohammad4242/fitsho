# Mobile Exercise Media Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use Markdown checkboxes for tracking.

**Goal:** Replace the crowded mobile exercise media card with a localized, gesture-driven, single-player media carousel and compact gender selector.

**Architecture:** Keep 'ExerciseDetailScreen' as the route-level owner of API queries, selected gender, and normalized index. Add small pure media/language helpers plus two focused native components: 'GenderMediaSelector' for accessible icon controls and 'ExerciseMediaCarousel' for the current player, index overlay, and thresholded 'PanResponder'. Use the existing 'presentation=unspecified' API behavior for availability discovery and retain the shared video-cache modules without card wiring.

**Tech Stack:** React Native 0.86, Expo SDK 57, 'expo-video', React Native 'PanResponder', TanStack Query, Vitest, Jest Expo, Testing Library React Native, existing Fitician tokens and Material Community icons.

**Spec:** 'docs/superpowers/specs/2026-09-09-mobile-exercise-card-design.md'

## Global Constraints

- Preserve the existing exercise route, detail response shape, gender-specific API requests, and shared video-cache modules.
- Render only the current media item; unmount the previous video when the key changes.
- Use the existing native RTL state as the card language source: RTL is 'fa', LTR is 'en'.
- Negative horizontal movement advances and positive horizontal movement goes back; require 48 logical pixels and a 1.2 horizontal-to-vertical ratio.
- Do not render offline-download controls, media labels, text media buttons, pagination buttons, or attribution in this card.
- Do not add a dependency or modify backend contracts.
- Stage and commit only the files for the current task; preserve all unrelated worktree changes.

---

### Task 1: Localized naming, direction, and media availability helpers

**Files:**
- Modify: 'mobile/ui/rtl.ts'
- Test: 'mobile/ui/rtl.test.ts'
- Modify: 'mobile/exercises/exerciseCopy.ts'
- Create: 'mobile/exercises/exerciseCopy.test.ts'
- Modify: 'mobile/exercises/exerciseMedia.ts'
- Modify: 'mobile/exercises/exerciseMedia.test.ts'
- Modify: 'mobile/exercises/exerciseApi.ts'
- Modify: 'mobile/exercises/exerciseApi.test.ts'

**Interfaces:**
- Produces 'MobileLanguage' and 'languageForDirection(isRTL?: boolean): MobileLanguage' from 'mobile/ui/rtl.ts'.
- Produces 'exerciseTitle(nameFa: string, nameEn: string, language?: MobileLanguage): string'; the default remains Persian for existing callers.
- Produces 'availableMediaPresentations(items: readonly ExerciseMediaItem[]): readonly ("male" | "female")[]', returning only genders with at least one renderable media path.
- Extends the existing mobile 'ExerciseApi.get' presentation parameter to '"male" | "female" | "unspecified"' so the existing backend inventory query is expressible without a route change.

- [ ] **Step 1: Write failing tests for language and media behavior**

~~~ts
it("maps the existing native direction to the card language", () => {
  expect(languageForDirection(true)).toBe("fa");
  expect(languageForDirection(false)).toBe("en");
});

it("shows only the selected localized exercise name with a safe fallback", () => {
  expect(exerciseTitle("پرس بالا سینه دمبل", "Dumbbell Incline Bench Press", "fa")).toBe("پرس بالا سینه دمبل");
  expect(exerciseTitle("پرس بالا سینه دمبل", "Dumbbell Incline Bench Press", "en")).toBe("Dumbbell Incline Bench Press");
  expect(exerciseTitle("", "Dumbbell Incline Bench Press", "fa")).toBe("Dumbbell Incline Bench Press");
});

it("returns only usable gender collections and ignores shared or broken media", () => {
  expect(availableMediaPresentations([
    mediaItem("male", "/media/male-1.mp4"),
    mediaItem("male", "/media/male-2.mp4"),
    mediaItem("female", ""),
    mediaItem("unspecified", "/media/shared.mp4"),
  ])).toEqual(["male"]);
});

it("forwards the existing unspecified presentation query", async () => {
  await api.get("press/advanced", "unspecified");
  expect(request).toHaveBeenCalledWith({
    method: "GET",
    path: "/api/v1/exercises/press%2Fadvanced?presentation=unspecified",
  });
});
~~~

- [ ] **Step 2: Run the focused tests and verify the intended failures**

Run: 'npm --prefix mobile exec vitest run ui/rtl.test.ts exercises/exerciseCopy.test.ts exercises/exerciseMedia.test.ts exercises/exerciseApi.test.ts'

Expected: FAIL because the language helper, English title selection, availability helper, and unspecified API forwarding are not implemented yet.

- [ ] **Step 3: Implement the smallest pure helpers and API type extension**

~~~ts
export type MobileLanguage = "fa" | "en";

export function languageForDirection(isRTL = I18nManager.isRTL): MobileLanguage {
  return isRTL ? "fa" : "en";
}

export function exerciseTitle(nameFa: string, nameEn: string, language: MobileLanguage = "fa"): string {
  const localized = (language === "en" ? nameEn : nameFa).trim();
  return localized || (language === "en" ? nameFa : nameEn).trim();
}
~~~

Implement 'availableMediaPresentations' by scanning only 'presentation === "male" | "female"' items and reusing 'isExerciseMediaRenderable'; keep the existing asset ordering and legacy fallback unchanged. Extend the 'ExerciseApi.get' union and preserve URL encoding.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: 'npm --prefix mobile exec vitest run ui/rtl.test.ts exercises/exerciseCopy.test.ts exercises/exerciseMedia.test.ts exercises/exerciseApi.test.ts'

Expected: PASS with no failures.

- [ ] **Step 5: Commit the helper boundary**

~~~bash
git add mobile/ui/rtl.ts mobile/ui/rtl.test.ts mobile/exercises/exerciseCopy.ts mobile/exercises/exerciseCopy.test.ts mobile/exercises/exerciseMedia.ts mobile/exercises/exerciseMedia.test.ts mobile/exercises/exerciseApi.ts mobile/exercises/exerciseApi.test.ts
git commit -m "feat(mobile): add localized exercise media helpers"
~~~

### Task 2: Accessible compact gender selector

**Files:**
- Modify: 'mobile/ui/icons.ts'
- Modify: 'mobile/ui/icons.test.ts'
- Create: 'mobile/exercises/GenderMediaSelector.tsx'
- Create: 'mobile/exercises/GenderMediaSelector.rntl.test.tsx'

**Interfaces:**
- Produces 'GenderMediaSelector({ available, selected, language, onChange })' where 'available' is a readonly male/female collection and 'onChange' receives only an available gender.
- Uses 'AppIcon' names 'genderMale' and 'genderFemale'; each visible control has 'accessibilityRole="radio"', a localized label, and selected accessibility state.

- [ ] **Step 1: Write failing native tests for icon mapping and selector behavior**

~~~tsx
test("renders only available genders with localized radio labels", () => {
  const onChange = jest.fn();
  render(
    <GenderMediaSelector
      available={["male"]}
      language="fa"
      onChange={onChange}
      selected="male"
    />,
  );

  expect(screen.getByRole("radio", { name: "ویدیوی مرد" })).toHaveAccessibilityState({ selected: true });
  expect(screen.queryByRole("radio", { name: "ویدیوی زن" })).toBeNull();
});

test("uses English labels and changes the selected gender", () => {
  const onChange = jest.fn();
  render(<GenderMediaSelector available={["male", "female"]} language="en" onChange={onChange} selected="male" />);

  fireEvent.press(screen.getByRole("radio", { name: "Female video" }));
  expect(onChange).toHaveBeenCalledWith("female");
});
~~~

- [ ] **Step 2: Run the native selector test and verify it fails**

Run: 'npm --prefix mobile run test:native -- GenderMediaSelector.rntl.test.tsx'

Expected: FAIL because the component and gender icon names do not exist.

- [ ] **Step 3: Add icon aliases and implement the compact selector**

Add 'genderMale: "gender-male"' and 'genderFemale: "gender-female"' to the existing icon map. Render an unlabelled 'View' group with 44-point press targets, selected turquoise background, subtle inactive surface, 'hitSlop={6}', and no visible text labels. Return 'null' when 'available' is empty.

- [ ] **Step 4: Run the native selector test and verify it passes**

Run: 'npm --prefix mobile run test:native -- GenderMediaSelector.rntl.test.tsx'

Expected: PASS.

- [ ] **Step 5: Commit the selector**

~~~bash
git add mobile/ui/icons.ts mobile/ui/icons.test.ts mobile/exercises/GenderMediaSelector.tsx mobile/exercises/GenderMediaSelector.rntl.test.tsx
git commit -m "feat(mobile): add accessible exercise gender selector"
~~~

### Task 3: Single-player gesture carousel

**Files:**
- Create: 'mobile/exercises/exerciseMediaCarousel.ts'
- Create: 'mobile/exercises/exerciseMediaCarousel.test.ts'
- Create: 'mobile/exercises/ExerciseMediaCarousel.tsx'
- Create: 'mobile/exercises/ExerciseMediaCarousel.rntl.test.tsx'

**Interfaces:**
- Produces 'clampMediaIndex(index: number, itemCount: number): number'.
- Produces 'resolveMediaSwipeIndex(currentIndex: number, deltaX: number, deltaY: number, itemCount: number, startedInControls?: boolean): number'.
- Produces 'ExerciseMediaCarousel({ items, selectedIndex, name, language, runtimeApiBaseUrl, onIndexChange })'.

- [ ] **Step 1: Write failing tests for threshold, direction, bounds, and one-player rendering**

~~~ts
it("advances on a deliberate horizontal left swipe and goes back on right swipe", () => {
  expect(resolveMediaSwipeIndex(0, -80, 4, 2)).toBe(1);
  expect(resolveMediaSwipeIndex(1, 80, 4, 2)).toBe(0);
});

it("ignores taps, vertical drags, control drags, and out-of-range movement", () => {
  expect(resolveMediaSwipeIndex(0, -20, 0, 2)).toBe(0);
  expect(resolveMediaSwipeIndex(0, -80, 80, 2)).toBe(0);
  expect(resolveMediaSwipeIndex(0, -80, 0, 2, true)).toBe(0);
  expect(resolveMediaSwipeIndex(1, -80, 0, 2)).toBe(1);
  expect(clampMediaIndex(9, 2)).toBe(1);
  expect(clampMediaIndex(2, 0)).toBe(0);
});
~~~

The native render test will provide two video items, mock 'expo-video', render the carousel, assert '1/2', and assert that only one 'VideoView' is present. It will also assert that a one-item collection has no pagination indicator.

- [ ] **Step 2: Run the focused carousel tests and verify the failures**

Run: 'npm --prefix mobile exec vitest run exercises/exerciseMediaCarousel.test.ts && npm --prefix mobile run test:native -- ExerciseMediaCarousel.rntl.test.tsx'

Expected: FAIL because the swipe model and component do not exist.

- [ ] **Step 3: Implement the pure swipe model and native surface**

Use 'PanResponder.create' with 'onStartShouldSetPanResponder: () => false', 'onMoveShouldSetPanResponder' gated by the 48-pixel threshold and 1.2 ratio, and a ref recording whether the gesture started in the bottom 64 pixels. Use 'resolveMediaSwipeIndex' on release, clamp through 'onIndexChange', and render only:

~~~tsx
<View testID="exercise-media-carousel" style={styles.frame}>
  <View testID="exercise-media-surface" {...panResponder.panHandlers}>
    <NativeExerciseMedia key={selectedItem.key} ... />
    {items.length > 1 ? <Text accessibilityLiveRegion="polite">{String(selectedIndex + 1) + "/" + String(items.length)}</Text> : null}
  </View>
</View>
~~~

Use 'isExerciseMediaRenderable' before rendering 'Media'; otherwise render the existing clean unavailable fallback. Keep 'nativeControls' true for videos and preserve normal taps.

- [ ] **Step 4: Run the focused carousel tests and verify they pass**

Run: 'npm --prefix mobile exec vitest run exercises/exerciseMediaCarousel.test.ts && npm --prefix mobile run test:native -- ExerciseMediaCarousel.rntl.test.tsx'

Expected: PASS.

- [ ] **Step 5: Commit the carousel**

~~~bash
git add mobile/exercises/exerciseMediaCarousel.ts mobile/exercises/exerciseMediaCarousel.test.ts mobile/exercises/ExerciseMediaCarousel.tsx mobile/exercises/ExerciseMediaCarousel.rntl.test.tsx
git commit -m "feat(mobile): add single-player exercise media carousel"
~~~

### Task 4: Integrate and remove obsolete card UI

**Files:**
- Modify: 'mobile/exercises/ExerciseDetailScreen.tsx'
- Modify: 'mobile/exercises/exercisePresentation.nativeContract.test.ts'

**Interfaces:**
- 'ExerciseDetailScreen' keeps the existing route, primary detail loading/error/offline handling, and profile-selected API behavior.
- The screen adds a non-blocking 'presentation=unspecified' inventory query, passes 'availableMediaPresentations' to 'GenderMediaSelector', and passes the current collection/index to 'ExerciseMediaCarousel'.

- [ ] **Step 1: Write failing integration/source-contract tests**

Add assertions that 'ExerciseDetailScreen.tsx' contains 'ExerciseMediaCarousel', 'GenderMediaSelector', 'languageForDirection', 'availableMediaPresentations', and the 'unspecified' inventory query, and does not contain 'ذخیره برای استفاده آفلاین', 'رسانه نمایش', 'videoMale', 'videoFemale', 'PresentationChip', 'downloadSelectedVideo', 'mediaSelector', or 'mediaSecondary'. Retain the pure reset/clamp coverage from Task 3 and verify the reset effect dependencies by source contract.

- [ ] **Step 2: Run the integration tests and verify they fail**

Run: 'npm --prefix mobile exec vitest run exercises/exercisePresentation.nativeContract.test.ts'

Expected: FAIL because the current card still renders the obsolete UI and does not use the new components.

- [ ] **Step 3: Replace only the card wiring**

Remove the card-specific 'PublicExerciseVideoCache' imports, cache state, cache effect, download/remove handlers, download props, attribution, text gender chips, text media choices, secondary bilingual title, and obsolete styles. Keep 'mobile/video/*' untouched.

Add:

~~~tsx
const language = languageForDirection();
const inventoryQuery = useQuery({
  enabled: slug !== undefined,
  queryFn: () => api.get(slug ?? "", "unspecified"),
  queryKey: [...exerciseKeys.detail(slug ?? ""), "media-inventory"],
});
const inventoryItems = inventoryQuery.data ? buildExerciseMediaItems(inventoryQuery.data) : mediaItems;
const available = availableMediaPresentations(inventoryItems);
~~~

Reset 'mediaIndex' on exercise, selected presentation, and normalized media-key changes. Guard gender changes with 'available.includes(next)'. Render a zero-padding hero 'Card', the new carousel, the localized title, and the selector; use responsive media sizing and existing dark/turquoise tokens. Pass 'language' into title, selector labels, text direction, and media fallback.

- [ ] **Step 4: Run the integration tests and verify they pass**

Run: 'npm --prefix mobile exec vitest run exercises/exercisePresentation.nativeContract.test.ts exercises/exerciseMedia.test.ts exercises/exerciseApi.test.ts && npm --prefix mobile run test:native -- GenderMediaSelector.rntl.test.tsx ExerciseMediaCarousel.rntl.test.tsx'

Expected: PASS with no obsolete card strings or controls rendered by the target source.

- [ ] **Step 5: Commit the integrated card**

~~~bash
git add mobile/exercises/ExerciseDetailScreen.tsx mobile/exercises/exercisePresentation.nativeContract.test.ts
git commit -m "feat(mobile): redesign exercise detail media card"
~~~

### Task 5: Full focused verification and handoff

**Files:**
- Verify only; no source changes unless a failing check identifies a regression caused by Tasks 1–4.

- [ ] **Step 1: Run mobile typecheck**

Run: 'npm run typecheck:mobile'

Expected: exit code 0.

- [ ] **Step 2: Run the complete mobile Vitest suite**

Run: 'npm --prefix mobile test'

Expected: all included mobile Vitest tests pass; report unrelated baseline failures separately if present.

- [ ] **Step 3: Run the complete native contract suite**

Run: 'npm --prefix mobile run test:native'

Expected: exit code 0.

- [ ] **Step 4: Run the available lint command against the changed mobile files**

Run: 'npm --prefix frontend exec oxlint -- ../mobile/ui/rtl.ts ../mobile/ui/icons.ts ../mobile/exercises/exerciseCopy.ts ../mobile/exercises/exerciseMedia.ts ../mobile/exercises/exerciseApi.ts ../mobile/exercises/GenderMediaSelector.tsx ../mobile/exercises/exerciseMediaCarousel.ts ../mobile/exercises/ExerciseMediaCarousel.tsx ../mobile/exercises/ExerciseDetailScreen.tsx'

Expected: exit code 0; if the frontend-installed binary rejects mobile config, record that exact limitation and rely on typecheck/tests rather than claiming lint coverage.

- [ ] **Step 5: Inspect the final diff and Git state**

Run: 'git diff --check HEAD~4..HEAD && git diff --stat HEAD~4..HEAD && git status --short --branch'

Confirm the diff contains only the spec/plan commits and focused mobile implementation files, with all pre-existing unrelated WIP still unstaged. Then report the Persian/English, gender, one/many/no-media, playback, swipe-control, and offline-UI scenarios with command-backed evidence.
