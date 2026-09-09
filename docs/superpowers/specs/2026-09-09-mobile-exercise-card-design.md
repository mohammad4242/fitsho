# Mobile Exercise Card Redesign

## Goal

Redesign the first exercise detail card in the Fitician mobile app so the current exercise media is the visual focus, while preserving the existing exercise API, route, and shared media infrastructure.

## Existing context

- `mobile/app/(member)/member/exercises/[slug].tsx` routes to `ExerciseDetailScreen`.
- `mobile/exercises/ExerciseDetailScreen.tsx` owns the detail query, selected gender state, media index, and the current media card.
- `ExerciseDetail` contains legacy primary media plus ordered `media_assets`; each asset has `presentation`, `role`, `sort_order`, `media_path`, and `media_type`.
- The backend already accepts `presentation=male`, `presentation=female`, and `presentation=unspecified`. Male/female requests return the selected collection plus unspecified shared assets; an unspecified request exposes the available media inventory.
- `mobile/ui/components/Media.tsx` owns `expo-video` player creation and native playback controls. The carousel must mount only its current item so unmounting tears down the previous player.
- Mobile currently has no independent language provider. `mobile/ui/rtl.ts` is the existing native direction source; the card derives `fa` from RTL and `en` from LTR, without introducing a second preference system.

## User-facing design

The card is a compact hero surface with this hierarchy:

```text
┌─────────────────────────────┐
│          current media      │
│                       1/2   │
├─────────────────────────────┤
│ localized exercise name     │
│                         ♂ ♀ │
└─────────────────────────────┘
```

- The media surface uses the existing dark/turquoise token system, rounded corners, and responsive sizing rather than a device-specific fixed height.
- The title renders only `name_fa` in Persian and only `name_en` in English, falling back to the other field only when the localized field is empty.
- Male/female controls use existing Material Community icon plumbing through `AppIcon`. Each control keeps a comfortable touch target, has a Persian/English accessibility label, and exposes selected state. Only genders with usable media are rendered.
- The current index is a small LTR numeric overlay such as `1/2`. It is hidden for a single item.
- Offline-download controls, display-media labels, text media buttons, pagination buttons, media attribution, and their card-only state/effects are removed from this card. Shared public-video cache modules remain available to other callers and tests.

## Architecture and data flow

1. Keep the existing detail query for the profile-selected collection and continue using `api.get(slug, "male" | "female")` when the user changes gender.
2. Add a read-only inventory query using the existing `presentation=unspecified` endpoint. It is used only to determine whether male and/or female controls are valid; inventory failures do not replace the primary detail error state.
3. Keep media normalization in `exerciseMedia.ts`. Add pure helpers to identify usable gendered collections. Preserve backend order and legacy fallback behavior.
4. Extract the current-media surface into `ExerciseMediaCarousel`. It receives the already-selected collection and index callback, renders one `Media` instance, and uses a `PanResponder` that activates only for horizontal movement beyond 48 logical pixels with a horizontal-to-vertical ratio above 1.2. A swipe with negative `dx` advances to the next item; positive `dx` moves back. This matches right-to-left Persian advancement and standard left-to-right physical swipe behavior.
5. The media surface ignores gesture starts in the bottom native-control region and never claims the responder on a normal tap. The existing `nativeControls` behavior therefore remains available for play/pause and seeking.
6. Reset the index to zero whenever the exercise, selected presentation, or normalized collection changes. Clamp every index update to the valid collection range.
7. Give the current media component a stable item key. When the item changes, the previous native video unmounts before the new one mounts, preventing multiple active players.
8. Derive the card language from `languageForDirection()` in the existing RTL module. Apply local `direction`, `writingDirection`, and font-family choices to the card/footer so LTR English layout is not inherited accidentally from the Persian screen shell.

## Empty and error behavior

- Empty, blank, placeholder, or invalid paths render the existing clean media-unavailable style instead of a broken player.
- A single usable item renders without pagination or unavailable gender controls.
- A gender with no usable media is omitted from the selector. If only one gender exists, only that icon is shown. If no gendered media exists, the selector is hidden.
- A failed inventory request leaves the current usable collection visible and shows no speculative unavailable gender. The main detail request keeps its existing loading, offline, error, and not-found states.
- A failed native media URL is handled by the existing player/media boundary; the card does not expose download or retry controls that are unrelated to this redesign.

## Test coverage

Add focused tests for:

- localized title selection and fallback in Persian and English;
- gender availability and shared/legacy media handling;
- API forwarding of `presentation=unspecified`;
- index reset/clamping and left/right swipe threshold/direction;
- native source contract, icon-only accessibility controls, absence of offline/text pagination UI, and one-current-player rendering.

Run the focused mobile Vitest/Jest tests, mobile typecheck, mobile lint, and the mobile build if the local environment supports it. Report any pre-existing unrelated failures separately.
