# Body Analysis Measurement Studio

## Scope

Improve only the measurement-confirmation step shown before a Body Analysis photo session.
Keep the existing profile loading, validation, confirmation, patch generation, save behavior,
navigation, and API contracts unchanged. Do not change the shared Profile/Onboarding visual
language as part of this work.

## Design direction

Use a focused "Measurement Studio" treatment: a calm, precise measurement surface that feels
like a body-progress calibration step rather than a generic form. The page remains Persian-first,
mobile-first, and uses existing Fitsho fonts and tokens.

- Canvas: existing light Fitsho canvas `#f7fbf9`.
- Ink: existing deep petrol `#102422`.
- Primary accent: Fitsho aqua `#50dfce` for active/focus states.
- Secondary accent: Fitsho coral `#ef826e` for the measurement marker and required attention.
- Utility accent: existing amber `#f4b942` for the confirmation checkpoint.
- Surface/line: white surfaces with existing `#d4e4df` and stronger teal lines.

Typography stays on the existing `Vazirmatn Variable` body face and `Lalezar` display face in
Persian, with no new font or dependency.

## Layout

The existing single card becomes a clear studio surface:

```text
┌──────────────────────────────────────────────┐
│ eyebrow        measurement status            │
│ title                                          │
│ short explanation                              │
│                                                │
│ ┌────────────── essential measures ─────────┐ │
│ │   height                    current weight │ │
│ │   large, high-contrast inputs              │ │
│ └────────────────────────────────────────────┘ │
│                                                │
│ ┌────────────── body proportions ───────────┐ │
│ │ shoulder       waist          hip          │ │
│ │ large inputs + concise guidance             │ │
│ └────────────────────────────────────────────┘ │
│ measurement note                               │
│ □ confirmation checkpoint                      │
│ back                         save and continue │
└──────────────────────────────────────────────┘
```

The signature detail is a narrow calibration rail and small unit treatment around the field
groups. It gives the form a recognizable measurement-tool identity without adding illustrations,
new assets, or distracting animation.

## Component and behavior boundaries

- Add semantic, Body Analysis-specific wrapper classes in `BodyAnalysisRequirementsStep`.
- Style the existing `MeasurementFields` output through those scoped classes; do not duplicate
  field logic or change `MeasurementFields` behavior.
- Keep the shared field labels, accessible `htmlFor`/`id` relationships, validation errors, and
  `aria-invalid`/`aria-describedby` wiring.
- Keep loading, load-error, save-error, disabled, unchecked, and confirmed states visually
  distinct.
- Keep the confirmation checkbox as the explicit gate for continuing.
- Use existing responsive behavior, with essential measures in two columns on comfortable
  widths and a single column on narrow mobile screens. Circumference fields collapse before they
  become cramped.
- Preserve visible keyboard focus, high contrast, touch targets, and `prefers-reduced-motion`.

## Testing

Add focused assertions for the new semantic studio regions and unchanged user behavior:

- the essential-measure and body-proportion groups render;
- all five fields remain discoverable by their labels;
- the continue action remains disabled until valid values and confirmation exist;
- a failed save still shows the existing error and does not advance.

Run the Body Analysis requirements tests, the relevant frontend test suite, lint, and production
build. No backend, database, or API changes are included.

## Out of scope

No changes to Profile/Onboarding forms, measurement validation ranges, persistence, Body Analysis
photo flow, analysis prompts, backend schemas, or workout integration.
