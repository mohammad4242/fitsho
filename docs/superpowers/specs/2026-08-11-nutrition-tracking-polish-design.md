# Nutrition Tracking Page Polish Design

## Scope

Polish only the adherence-trend and off-plan meal areas of the existing member nutrition tracking
page. Preserve current nutrition calculations, API requests, validation guards, date filtering,
language direction, and unrelated page sections.

## Adherence Trend Accordion

- Replace the always-expanded trend section with a controlled accordion whose initial state is
  closed on every page mount.
- Keep the `روند پایبندی` heading, the existing start-date field, and a subtle chevron visible in
  the closed state.
- Use a dedicated button for the expandable heading and keep the date field outside that button so
  changing the date never toggles the accordion.
- Expose `aria-expanded` and `aria-controls` on the button. Mark the animated content unavailable
  to keyboard and assistive-technology navigation while closed.
- Animate one grid row from zero to full height with matching opacity. Rotate the chevron from the
  closed to open direction on the same transition. Disable the motion when reduced motion is
  requested.
- Keep adherence and tracking-history requests active exactly as they are now. Changing the date
  continues to reload both real datasets even when the accordion is closed.
- Place daily adherence rows, the optional weight note, and entry history inside the collapsible
  content.

## Off-plan Meal Form

- Keep the existing manual-entry disclosure and the same state variables and submission functions.
- Split the expanded content into two compact visual groups:
  - Exact catalogue entry: food selection, quantity in grams, and `ثبت از کاتالوگ`.
  - Quick estimate: approximate calories and `ثبت تقریبی`.
- Retain native semantic `select`, `input`, and `button` elements for accessibility and current
  behavior, while fully styling their visible surface with Fitsho tokens so browser-default chrome
  is not exposed.
- Give every field a visible label, dark inset surface, teal focus state, and sufficient touch
  target. Add a custom visual chevron to the food selection and a fixed unit suffix to numeric
  fields without changing submitted values.
- Make catalogue submission visually obvious and make approximate submission the primary full
  action within its group. Preserve existing disabled states and validation guards.
- Use RTL-safe logical properties. Stack controls at narrow mobile widths and use a compact grid
  when space allows.

## Error Handling and Data Flow

No new requests or error states are introduced. Catalogue submission still calls
`addCatalogueFoodEntry`; approximate submission still calls `addQuickApproximation`; successful
operations still reload today's tracking summary. Existing errors and busy state remain unchanged.

## Testing and Verification

- Test that the trend rows are collapsed initially, the date field remains available, and repeated
  header clicks update the accessible open state.
- Test that changing the closed accordion's date still calls both adherence and history APIs with
  the selected start date.
- Test the catalogue and approximate forms through their real semantic controls and assert the
  existing API payloads remain unchanged.
- Run the focused nutrition workflow tests, full frontend tests, lint, and production build.
- Verify the served tracking page at narrow mobile width and confirm no horizontal overflow or raw
  browser-style field surface remains.
