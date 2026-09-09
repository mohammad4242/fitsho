import { readFile } from "node:fs/promises";

import { expect, it } from "vitest";

it("renders real exercise media in catalogue cards", async () => {
  const source = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain('from "./ExerciseMedia"');
  expect(source).toContain("mediaType={exercise.media_type}");
  expect(source).toContain("path={exercise.media_path}");
  expect(source).toContain("styles.cardMedia");
});

it("keeps network media loading visible and falls back safely", async () => {
  const source = await readFile(new URL("./ExerciseMedia.tsx", import.meta.url), "utf8");

  expect(source).toContain("onFirstFrameRender");
  expect(source).toContain("onError");
  expect(source).toContain("loadingOverlay");
  expect(source).toContain("isExerciseMediaRenderable");
});

it("uses the compact localized media carousel card", async () => {
  const source = await readFile(new URL("./ExerciseDetailScreen.tsx", import.meta.url), "utf8");

  expect(source).toContain("<ExerciseMediaCarousel");
  expect(source).toContain("<GenderMediaSelector");
  expect(source).toContain("exercise-detail-breadcrumb");
  expect(source).not.toContain("<ScreenHeader");
  expect(source).toContain('direction={language === "en" ? "ltr" : "rtl"}');
  expect(source.indexOf('testID="exercise-detail-breadcrumb"')).toBeLessThan(source.indexOf("<ExerciseMediaPanel"));
  const mediaPanel = source.slice(source.indexOf("function ExerciseMediaPanel"), source.indexOf("function ExerciseInformation"));
  expect(mediaPanel.indexOf("<GenderMediaSelector")).toBeLessThan(mediaPanel.indexOf('testID="exercise-media-card-title"'));
  expect(source).toContain("languageForDirection");
  expect(source).toContain("availableMediaPresentations");
  expect(source).toContain('api.get(slug ?? "", "unspecified")');
  expect(source).toContain("styles.infoCard");
  expect(source).not.toContain("ذخیره برای استفاده آفلاین");
  expect(source).not.toContain("رسانه نمایش");
  expect(source).not.toContain("exerciseSecondaryTitle");
  expect(source).not.toContain("PresentationChip");
  expect(source).not.toContain("PublicExerciseVideoCache");
});

it("matches the web media aspect ratio while keeping native media controls", async () => {
  const source = await readFile(new URL("./ExerciseMediaCarousel.tsx", import.meta.url), "utf8");

  expect(source).toContain("aspectRatio: 4 / 3");
  expect(source).toContain("nativeControls");
  expect(source).toContain("MEDIA_SWIPE_THRESHOLD");
});
