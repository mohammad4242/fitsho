# Program Engine Issue 3: Safe Construction Recovery

## Problem

Session construction currently treats every required movement-pattern slot as
fatal. A valid profile can therefore fail after eligibility has correctly
removed unsafe or unavailable exercises. Existing split fallback cannot recover
when every candidate split contains the same unfillable required slot.

## Design

Keep eligibility, caution filtering, equipment filtering, and final safety
validation unchanged as hard constraints. During session construction recovery,
relax a required slot only when the catalog contains candidates for that slot
but all of them were rejected by hard constraints. The slot is omitted and the
session is filled from already-eligible compatible exercises. No rejected
candidate is selectable.

The recovery records the affected slot and reason codes in the session draft,
construction trace, and final program trace. Existing split fallback remains the
next recovery path when session construction still cannot succeed.

Final validation recognizes only the explicitly recorded unavailable pattern or
coverage requirement. It continues to reject every selected exercise that
violates caution, equipment, support, activity, or prescription constraints.

## Verification

Regression coverage will include direct eligibility/layout recovery, the exact
four-day home dumbbell knee-caution profile, template/layout fallback tracing,
safe/equipment constraint preservation, and a genuinely unsatisfiable catalog.
