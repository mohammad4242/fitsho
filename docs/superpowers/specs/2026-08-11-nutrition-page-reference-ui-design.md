# Nutrition Page Reference UI Design

## Scope

Update only the existing member nutrition estimate page to match the requested parts of
`taghziye.jpg`. Preserve nutrition APIs, calculation rules, plan generation behavior, RTL/LTR
support, responsive layout, and unrelated page sections.

## Calorie Goal

- Rename the Persian calorie label from `هدف انرژی` to `کالری هدف` and update its accessible
  region name consistently.
- Continue deriving the displayed target through the page's existing `energyTarget` selection,
  including its current weekly-plan fallback behavior. Do not introduce a fixed value.
- Add a small reusable animation hook driven by one `requestAnimationFrame` timeline. It returns
  a normalized progress value from zero to one.
- Use that same normalized value for both outputs: multiply it by the real calorie target for the
  displayed number, and by the real calorie target for `ProgressRing`. This guarantees that the
  number and ring start and finish on the same frames.
- Finish with the exact target and a 100% ring. If reduced motion is requested, render the final
  state immediately.
- Keep missing-target behavior unchanged and make the card slightly more compact through scoped
  nutrition-page CSS.

## Doctor Supervision

Insert a compact section after the scientific-details block and before the weekly-plan area. Its
header contains a doctor icon and the title `تحت نظر پزشک`. The four items are:

- `مکمل‌های من`, linked to the existing supplements page.
- `آزمایشات من`, linked to the existing labs page.
- `تأیید برنامه غذایی`, showing the existing weekly plan review state.
- `راهنمایی‌های پزشک`, showing whether physician-visible guidance exists on the current plan.

The section reads only data already loaded by the page. It adds no API request or backend state.
A red dot and pending copy appear only when an existing plan is still waiting for physician
approval. Approved plans do not show a pending indicator. With no plan, the approval item uses a
neutral not-yet-created state rather than claiming a pending physician review.

## Weekly Nutrition Plan CTA

When no weekly plan exists, replace the default eyebrow, heading, and description with one compact
button labelled `ساخت برنامه تغذیه هفتگی`. Preserve the existing generation request, disabled busy
state, generated-plan rendering, and outcome-specific error or safety feedback after an attempt.

## Styling and Accessibility

- Follow existing Fitsho surface, border, aqua, coral, typography, and radius tokens.
- Use a two-column supervision grid where space allows and a single-column layout on narrow
  screens.
- Preserve page direction from the active language and provide complete English copy.
- Keep links and buttons semantic, retain the progressbar label and values, and expose status copy
  without relying on color alone.

## Testing

- Add a test that controls animation frames and proves the calorie number and progress ring begin
  at zero and end together at the real target and 100%.
- Add tests for the four doctor-supervision items, existing destinations, and pending indicator.
- Add a test that the compact CTA exists and the removed default heading and description do not.
- Run the focused nutrition page test, the full frontend test suite, frontend lint, and frontend
  build.
