# Nutrition Toman Money Design

## Goal

Use Toman consistently in Fitsho's member-facing nutrition budget and price interfaces while
preserving the existing IRR persistence and API contracts. Run one additional real price-refresh
cycle using the established provider workflow.

## Price Refresh

The existing price-update service remains the sole ingestion path. A manual run will use its
configured free providers, normalization, outlier handling, and reference-price selection. The
run is isolated per provider and per food. It never replaces an accepted reference with a failed
or suspicious candidate, and it retains immutable history.

## Money Boundary

Member UI accepts and displays whole Toman. The frontend normalizes Persian/Latin digits and
thousands separators, stores an unformatted Toman value in component state, then converts to IRR
only at the existing API boundary. API response fields ending in `_irr` and existing database
columns stay unchanged for backward compatibility.

## Surfaces

- Nutrition onboarding and profile budget fields display a Toman label and grouped digits while
  typing.
- Weekly-plan budget/cost and physician weekly cost display Toman instead of IRR.
- Food catalogue prices continue to use their existing Toman reference values. Any legacy IRR
  display is converted before rendering.

## Validation

The numeric formatter accepts grouped Latin or Persian digits, strips formatting on submit, and
rejects invalid values through existing form validation. Tests cover conversion, grouping, existing
IRR API payload compatibility, Toman display, and the manual refresh command/service outcome.
