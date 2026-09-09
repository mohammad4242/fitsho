# Web ↔ Native component parity

This matrix records the shared visual contract before page migrations. The native implementation
must extend these primitives rather than create page-local copies. Values are sourced from the
current web token/primitives CSS and the current `mobile/ui` components.

## Token and primitive mapping

| Web source | Native source | Current parity | Phase 1 intent |
| --- | --- | --- | --- |
| `tokens.css` canvas/petrol/raised/ink/muted/aqua/status colors | `mobile/ui/tokens.ts` `colors` | Palette is already closely aligned; native also has media/status atmosphere tokens | Reuse existing tokens; add only repeated missing values |
| `tokens.css` spacing 1–8 | `tokens.ts` `spacing` 1–8 | Same 4/8/12/16/24/32/48/72 rhythm | Keep a single scale |
| `tokens.css` radii and shadows | `tokens.ts` `radii`/`shadows` | Values are adapted for native elevation; some native cards use stronger cinematic treatment | Quiet dark surfaces by default; keep hero treatment source-led |
| `index.css` body Persian typography | `tokens.ts` `bodyPersian: Vazirmatn` | Present | Preserve RTL text alignment and font scaling |
| `index.css` `.fitsho-display` | `tokens.ts` `displayPersian: Lalezar`, English `Sora` | Present | Lalezar only for short display headings |
| `index.css` numeric/English utility type | `tokens.ts` `bodyEnglish/displayEnglish: Sora` | Present | Keep numbers and mixed-script labels direction-safe |
| `.fitsho-page` / `.app-shell` | `Screen`, `SafeAreaView`, `KeyboardAvoidingView` | Native owns safe area and keyboard | Do not replace with a WebView |
| `.fitsho-card` / `.fitsho-data-panel` | `Card` default/raised | Surface, border, radius, elevation are available | Do not globally turn cards into hero/glass |
| `.fitsho-card--interactive` | `Card onPress`, `Pressable` | Press feedback and 48 dp minimum exist | Keep full-region press targets and accessibility |
| `.fitsho-button` / `.fitsho-button-secondary` | `Button` primary/secondary/ghost/danger | Semantics and loading/disabled state exist; radius is native medium, not web pill | Match relative hierarchy; do not alter handlers |
| `.fitsho-section-heading` | `SectionHeader` | Eyebrow/title/action exists | Use for sections; add `PageHeading` only when current primitives cannot express web heading |
| Web compact heading without brand row | No direct equivalent; `ScreenHeader` always has FITICIAN row | Gap: current native can introduce a brand row where web starts compact | Phase 1 `PageHeading` candidate |
| `.fitsho-metric-strip` | `MetricStrip` | Three-cell strip exists; web context may need four cells | Reuse/extend only if repeated, with logical dividers and wrapping |
| `.fitsho-progress-ring` | `MetricRing` using `react-native-svg` | Value-driven accessible ring exists | Never render a fake partial value |
| `.fitsho-status` | `Notice` | Info/success/warning/danger/offline variants exist | Keep state concise and user-facing |
| `.fitsho-input` / auth input rules | `FormField` / `TextField` | Labels, errors, direction, font scaling, keyboard props exist | Keep keyboard-safe native forms |
| HTML `details/summary` | `DisclosureCard` | Pressable expansion with accessibility state exists | Match collapsed/expanded hierarchy, not HTML mechanics |
| `.fitsho-grouped-list` | No shared native primitive | Gap: More currently uses individual `Card`s | Phase 1 `GroupedList` candidate |
| Web modal/dialog | `Sheet` / `Dialog` in `Overlay.tsx` | Native modal boundary, safe bottom edge, Android close callback | Preserve native sheet/dialog behavior |
| Web image/video components | `Media`, `ExerciseMedia`, carousel/video cache | Native lifecycle/cache/fallback exists | Stable aspect ratios; pause on navigation/background |
| Web SVG `AppIcon` | Native `AppIcon` | Shared icon system exists | Use icons instead of text glyphs/emoji for directional controls |
| Web loading indicator/skeleton | `Skeleton`, `StateSkeleton`, route guard loading | Shape loading exists; source-level baseline saw a Vitest/RNTL config mismatch | Keep loading honest and accessible |
| Web mobile bottom nav | Expo Router `Tabs` + safe-area inset | Native tab semantics and keyboard hiding exist; four tabs currently | Phase 2 adds Body Progress as fifth capability-aware destination |

## Component contracts to carry into page work

### Layout

- `Screen` owns `SafeAreaView`, scrolling, RTL direction, keyboard avoidance, and responsive
  content width.
- `contentWidth="reading"` is the default for dense phone-readable member pages.
- Native layouts may stack or use a Sheet where web uses desktop columns, but preserve web order
  and emphasis.

### Surfaces

- Default surface: quiet dark background, restrained border, rounded card, minimal shadow.
- `CinematicSurface`/hero treatment is allowed only when the web source is media-led or
  atmospheric. It is not a global wrapper.
- Cards with actions remain accessible pressables with a minimum 48 dp dimension.

### Text and direction

- Persian body and form text: Vazirmatn, right aligned, `writingDirection: "rtl"`.
- Short Persian display headings: Lalezar.
- English words, identifiers, and numeric display: Sora with explicit LTR where needed.
- Use logical row direction/dividers; do not mirror exercise/body media.
- Long Persian labels must wrap rather than clip the primary action.

### States

- Loading, empty, error, offline/stale, pending approval, and historical are distinct.
- Cached/offline data stays visible with a compact state notice where the contract allows it.
- Raw reason codes, provider messages, schema metadata, and internal keys are not component copy.
- Missing values stay unavailable (`—` or equivalent), never zero or fabricated progress.

## Phase 1 test targets

The shared bridge gate must have rendered tests for:

- RTL logical ordering and LTR numeric/English content;
- selected segmented option, disabled/loading state, and 48 dp interaction contract;
- `PageHeading` with and without an opposite-side action;
- `GroupedList` press behavior and accessible labels;
- unchanged native Home, a form, a list, and a modal after primitive changes.
