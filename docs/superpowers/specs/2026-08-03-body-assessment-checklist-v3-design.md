# Body Assessment Checklist v3

## Goal

Replace the current strength/lag-oriented visual assessment with a coach-oriented
checklist that supplies deterministic, program-ready priorities per body area and
preserves body-progress comparisons.

## Profile Measurements

Add optional centimetre fields below height and current weight:

- shoulder circumference
- waist circumference
- hip circumference
- measurement timestamp

The fields are optional for existing users. The profile continues to work without
them, but a goal suggestion records the missing measurement limitation.

## Assessment Contract

Create schema version `3.0`. It evaluates the existing 13 body areas. Every area
contains a checklist item for front, side, and back. Each item is one of:

- excellent
- good
- average
- needs_attention
- focus_priority
- not_assessable

Each checklist item has concise Persian evidence and can use `not_assessable` when
that view cannot responsibly show the area. Each area also has an overall rating,
an evidence-based Persian summary relative to the full visible physique, and an
allowed program emphasis.

The model continues to use the existing three-view coach rubric: visible size,
contour, width, thickness, shoulder-to-waist taper, upper/lower balance, and
obvious image-left/image-right differences. It does not estimate body-fat
percentage, diagnose health, injury, posture, or mobility, and does not prescribe
exercises or rehabilitation.

## Goal Suggestion

The v3 output includes one suggestion selected from the current product goals:

- lose_weight
- maintain_weight
- build_muscle
- gain_weight

The suggestion is advisory and never overwrites the user's selected profile goal.
It explains its visible and measurement-supported reasoning in Persian and records
which provided inputs were unavailable. It may use the user-selected goal, height,
weight, shoulder/waist/hip measurements, and non-medical visible proportions. It
does not report a body-fat percentage or a medical claim.

## Program Projection

The backend converts the checklist into the existing stable normalized projection:

- excellent and good can become visible strengths only when supported across views
- needs_attention becomes moderate attention
- focus_priority becomes priority
- not_assessable becomes uncertainty
- average becomes neutral

The deterministic workout engine consumes this compatibility projection. It does
not depend on presentation labels or free text.

## Progress

The existing per-area progress table stays unchanged. A deterministic overall
indicator is derived from the area comparisons:

- improved
- stable
- needs_attention
- insufficient_data

The UI shows the overall indicator alongside the existing per-area comparison.

## Data and API

Add a versioned visual v3 result beside the existing normalized compatibility
projection. Version 1 and version 2 results remain readable. The API returns the
appropriate visual result for each analysis version.

## Verification

- Profile validation and API tests for optional centimetre measurements.
- Schema validation for all 13 areas, all three view checklist entries, goal
  suggestion, and forbidden medical/body-fat claims.
- Projection tests for checklist-to-workout priority mapping.
- Progress tests for the overall indicator.
- Frontend tests for profile measurements, checklist display, goal suggestion,
  historical result rendering, and overall progress indicator.
- A non-persisted live provider validation using anonymized photos.
