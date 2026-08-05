# Post-login profile wizard design

## Scope

Redesign only the signed-in profile experience at `/profile`. Public onboarding at
`/get-started` remains a question-by-question flow. Backend APIs and stored profile
models remain unchanged.

## Experience

The signed-in profile is one internal three-step flow:

1. Personal information
2. Training information
3. Nutrition information

Each step uses the full profile content area, keeps all fields for that category in
one vertically scrollable page, and shows a visible three-stage progress header.
Back and Next controls stay at the bottom of every step. The first Back control
returns to the dashboard. The final action saves nutrition details and remains on
the nutrition step with a localized success message.

Previously saved values are loaded into their controls. Values collected during
public onboarding are shown for review and are not asked again in a guided flow.
Persian uses RTL layout and Persian labels; English uses LTR layout and English
labels.

## Product-mode behavior

- Training: personal and training steps are editable. The nutrition step is visible
  as optional and must not block navigation or dashboard use.
- Nutrition: personal information is editable where supported. Training information
  is optional; nutrition-only members without a training profile see an optional
  empty state instead of required training questions. Nutrition details are editable.
- Training and nutrition: all three steps are editable.

Profile completion after sign-in remains optional for every product mode.

## Components and data flow

`ProfilePage` owns the active step and renders a shared progress/navigation frame.
The personal and training pages reuse the existing profile field groups and profile
patch API. The nutrition page reuses the existing post-account nutrition form and
nutrition API, embedded inside the same profile flow instead of navigating to a
separate guided onboarding route.

Personal and training edits remain local while moving between steps. Moving forward
validates only the current category. A changed category is saved before advancing;
unchanged values advance without an API request. API failure keeps the member on the
same step with their edits intact and shows the existing localized error.

The legacy `/nutrition-profile` route may redirect to `/profile` so existing links do
not break. The account menu continues to use `/profile` as the single profile entry.

## Testing

Frontend tests cover:

- the three ordered signed-in steps and localized progress labels;
- Back and Next navigation, including dashboard return from the first step;
- category-scoped validation and save-before-advance behavior;
- nutrition-only optional training state;
- the nutrition form embedded as the third scrollable step;
- unchanged public onboarding behavior;
- RTL/LTR behavior and the legacy nutrition-profile redirect.

Run the complete frontend test suite, lint, production build, and `git diff --check`.
