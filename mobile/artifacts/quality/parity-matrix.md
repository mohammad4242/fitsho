# Fitician Android Parity Matrix

| Area | Implemented evidence | Remaining evidence or work | Status |
|---|---|---|---|
| Shared visual system | Existing theme, buttons, cards, states, disclosure cards, media primitives | Physical-device visual review | Automated only |
| Member Home | Media-first hierarchy and quick actions; source/native tests | Required RNTL interaction test; phone screenshots and actions | Partial |
| Workout plans | Plan hierarchy and exercise-library destination | Required RNTL interaction test; phone empty/loading/error/active states | Partial |
| Exercise catalogue | Search, primary chips, advanced filter sheet, detail disclosure | Complete active-filter count/removal; required RNTL test; phone media/fallback review | Partial |
| Nutrition tracking | Tracking presentation, catalogue destinations, thumbnail fallbacks | Required RNTL interaction test; phone loading/error/empty/data review | Partial |
| Nutrition catalogues | Guarded plan, food, and meal routes with real API data | Phone navigation, media, disclosure, and fallback review | Automated only |
| Body Analysis | Existing privacy-preserving capture and wizard flow | Required RNTL interaction test; real camera/privacy/device evidence | Partial |
| Authentication | Existing Email/Mobile/Google routes and guards | Phone keyboard, error, loading, and draft-hydration verification | Unverified on device |
| Profile | Existing profile and specialist destinations | Phone hierarchy, edit, media, and accessibility verification | Unverified on device |
| Reliability | Typecheck, unit/native/foundation tests and lint pass | Resolve validator drift and high dependency advisory through separate dependency decision | Partial |
| Accessibility | Existing labels, roles, and touch-target helpers | TalkBack, focus order, contrast, text scaling, and reduced-motion evidence | Unverified on device |
| Performance | Existing performance contract tests | Cold start, route transition, list scroll, image loading, and camera measurements | Unverified on device |

## Required interaction-test gaps

- `mobile/home/MemberHomeScreen.rntl.test.tsx`
- `mobile/workouts/WorkoutPlansScreen.rntl.test.tsx`
- `mobile/exercises/ExerciseCatalogScreen.rntl.test.tsx`
- `mobile/nutrition/NutritionTrackingSection.rntl.test.tsx`
- `mobile/bodyAnalysis/BodyAnalysisWizard.rntl.test.tsx`

## Acceptance gate

Automated completion requires the five interaction suites, corrected exercise-filter behavior, green project checks, and an explicit dependency-resolution decision. Final visual acceptance additionally requires a current APK and physical-device evidence.
