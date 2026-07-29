# Public Video Landing Design

## Goal

Replace the guest entry experience with a full-screen, three-scene Fitsho landing page. It must feel premium and energetic before sign-in while keeping the existing backend, database, authentication, and protected-app contracts unchanged.

## Routing

- Guests reaching `/` see the new landing page.
- Every `شروع رایگان` CTA navigates to `/register`.
- Existing `/login` and `/register` routes remain available.
- Authenticated users reaching `/` continue to `/dashboard`.

## Media Story

- Scene one uses the owner-supplied `landing.mp4` as the full-viewport hero.
- Scene two uses the second supplied video for the personalized-plan chapter.
- Scene three uses the third supplied video for the progress chapter.
- Each scene fills one viewport. Text fades up only when its scene becomes active through an IntersectionObserver.
- Only the active scene plays; inactive videos pause and use `preload="none"` after the first scene.
- The five supplied images are optimized fallback artwork for the three scenes and still media on signed-in screens. They are not stretched as desktop hero backgrounds beyond their native useful resolution.

## Visual Direction

- Large Lalezar Persian display copy, short supporting text, and a large aqua `شروع رایگان` CTA in every scene.
- Dark petrol overlays guarantee readable text over video.
- The story uses: `از امروز، قوی‌تر.`; `بدون حدس، با برنامه.`; `هر تکرار، نزدیک‌تر.`
- The signed-in application keeps its fast, practical UI. It receives selected still imagery as restrained visual accents; it does not autoplay background video across forms, profile, catalog, or admin screens.

## Performance and Accessibility

- Video is muted, looped, and inline. The first scene may preload metadata; later scenes load only near the viewport.
- `prefers-reduced-motion`, a failed video, and narrow/slow mobile conditions show the mapped image fallback with all text and CTAs preserved.
- Keyboard navigation, route guards, Persian/English behavior, and focus styles remain intact.

## Scope and Verification

- Copy owner-provided media from the root `image_videos` folder into versioned frontend assets, with stable descriptive filenames.
- Add tests for guest root routing, all three CTAs, authenticated root redirect, and reduced-motion fallback semantics.
- Run frontend tests, lint, build, and a local API/frontend smoke check.
- No new endpoint, schema, migration, API request, or data model is added.
