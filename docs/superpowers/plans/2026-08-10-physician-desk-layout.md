# Physician Desk Layout Implementation Plan

1. Add focused frontend tests for the physician desk sidebar, tabbed case workspace, and approved
   read-only state; run them to establish the expected failure.
2. Restructure `PhysicianNutritionReviewPage` around the existing coach workspace layout: physician
   desk hero, responsive queue sidebar, explicit selected-case state, and safe empty state.
3. Move existing plan, laboratory, supplement, and notes controls into the four case tabs without
   changing their API contracts or access behaviour.
4. Add scoped CSS derived from the coach workspace layout, including RTL sidebar placement and
   responsive single-column fallback.
5. Run focused and full frontend tests, lint, and production build; commit and push only this
   feature's files.
