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
  expect(mediaPanel.indexOf("<ExerciseMediaCarousel")).toBeLessThan(mediaPanel.indexOf("<GenderMediaSelector"));
  expect(mediaPanel.indexOf("<GenderMediaSelector")).toBeLessThan(mediaPanel.indexOf('testID="exercise-media-card-title"'));
  expect(source).toContain("languageForDirection");
  expect(source).toContain("availableMediaPresentations");
  expect(source).toContain('api.get(slug ?? "", "unspecified")');
  expect(source).toContain("styles.infoCard");
  expect(source).not.toContain("saveOffline");
  expect(source).not.toContain("downloadSelectedVideo");
  expect(source).not.toContain("downloadHint");
  expect(source).not.toContain("offlineReadyHint");
  expect(source).not.toContain("removeDownload");
  expect(source).not.toContain("PublicExerciseVideoCache");
  expect(source).not.toContain("ExpoPublicExerciseVideoStore");
  expect(source).not.toContain("validatePublicExerciseVideoPath");
  expect(source).not.toContain("detailCopy[language].stale");
  expect(source).not.toContain("رسانه نمایش");
  expect(source).not.toContain("exerciseSecondaryTitle");
  expect(source).not.toContain("PresentationChip");
  const mediaTitle = source.slice(source.indexOf("mediaTitle:"), source.indexOf("mediaTitleEnglish:"));
  expect(mediaTitle).toContain('alignSelf: "stretch"');
  expect(mediaTitle).toContain('textAlign: "center"');
});

it("gives the gender selector the full centered media-card row", async () => {
  const source = await readFile(new URL("./GenderMediaSelector.tsx", import.meta.url), "utf8");
  const container = source.slice(source.indexOf("container:"), source.indexOf("ltr:"));

  expect(container).toContain('justifyContent: "center"');
  expect(container).toContain('width: "100%"');
});

it("matches the web media aspect ratio while keeping native media controls", async () => {
  const source = await readFile(new URL("./ExerciseMediaCarousel.tsx", import.meta.url), "utf8");

  expect(source).toContain("aspectRatio: 4 / 3");
  expect(source).toContain("nativeControls");
  expect(source).toContain("MEDIA_SWIPE_THRESHOLD");
});

it("keeps exercise catalogue and detail rows on native RTL ordering", async () => {
  const catalogSource = await readFile(new URL("./ExerciseCatalogScreen.tsx", import.meta.url), "utf8");
  const detailSource = await readFile(new URL("./ExerciseDetailScreen.tsx", import.meta.url), "utf8");
  const genderSource = await readFile(new URL("./GenderMediaSelector.tsx", import.meta.url), "utf8");

  expect(catalogSource).not.toContain('flexDirection: "row-reverse"');
  expect(catalogSource).not.toContain('alignItems: "flex-end"');
  expect(detailSource).not.toContain('flexDirection: "row-reverse"');
  expect(detailSource).not.toContain('alignItems: "flex-end"');
  expect(genderSource).not.toContain('flexDirection: "row-reverse"');
  expect(detailSource).toContain('direction={language === "en" ? "ltr" : "rtl"}');
  expect(detailSource).toContain('language === "en" ? (');
});
