# Nutrition Toman Money Implementation Plan

1. Add frontend unit tests for Toman normalization, grouping, parsing, and IRR conversion.
2. Add a shared money-formatting utility and apply it to nutrition onboarding/profile budget input
   while preserving the existing IRR API payload.
3. Convert member-facing weekly-plan and physician cost/budget displays to Toman.
4. Run the existing manual price-update workflow once, inspect its persisted outcome, and retain its
   normal safety behaviour for provider failures and suspicious quotes.
5. Run focused and full frontend/backend tests, commit, and push the isolated change.
