# Phase 8: Template Selection Audit Design

## Scope

Phase 8 adds observability to deterministic structural-template selection. It does not change
eligibility, scores, ranking, template structure, or any downstream personalization stage.

## Architecture

`template_selector.py` will produce one immutable `TemplateSelectionResult`. It contains the
ranked `TemplateRankingResult` candidates, hard rejections, selected candidate, and optional
tie-break record. Each ranking result holds the exact `TemplateScore` used by the current sorter
plus stable reason codes. No trace or explanation path may call the scorer again.

The engine will append the result's serialized `template_selection` entry to the existing
persisted decision trace before template construction. Existing downstream trace entries remain
separate and unchanged.

## Decision Trace Contract

The entry has this shape:

```text
{
  stage: "template_selection",
  requested_days: int,
  experience_level: str,
  templates_considered: int,
  hard_rejections: [
    {slug: str, reason_codes: [str]}
  ],
  candidates: [
    {
      slug: str,
      score: {
        priority: int,
        body_analysis: int,
        goal: int,
        sex: int,
        fallback: int,
        total: int
      },
      reason_codes: [str]
    }
  ],
  selected: str | null,
  tie_break: null | {
    score: int,
    tied_slugs: [str],
    selected_by: "slug_descending",
    selected: str
  }
}
```

Templates failing hard eligibility appear only in `hard_rejections`; they never receive a score.
Candidates are emitted in the exact deterministic ranking order. Reason-code lists and rejection
lists use stable ordering.

Hard-rejection codes are `DAYS_MISMATCH`, `EXPERIENCE_LEVEL_MISMATCH`, and
`CORE_SLOT_UNRESOLVABLE`. Multiple applicable codes may be recorded for one template.

Scoring reason codes are:

- `EXPLICIT_PRIORITY_EXACT_MATCH`
- `EXPLICIT_PRIORITY_REGIONAL_MATCH`
- `BODY_ANALYSIS_CLEAR_LAG_MATCH`
- `BODY_ANALYSIS_MILD_LAG_MATCH`
- `GOAL_STRENGTH_BIAS_MATCH`
- `GOAL_COMPOUND_FOCUS_MATCH`
- `GOAL_BALANCED_MATCH`
- `SEX_PRIOR_GLUTE_MATCH`
- `SEX_PRIOR_LOWER_MATCH`
- `SEX_PRIOR_UPPER_MATCH`
- `SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY`
- `BALANCED_FALLBACK`

Reason-code attachment observes the same capped component result. Codes describe contributing
signals, except `SEX_PRIOR_DISABLED_BY_EXPLICIT_PRIORITY`, which records the existing explicit
disable rule.

## Coach Explanation

A pure formatter accepts only the structured template-selection trace and returns a concise
Persian and English explanation. It summarizes structural eligibility, the strongest contributing
signal, optional supporting signals, and states that exercise, volume, and session personalization
happened afterward. It does not inspect profile data, templates, or rerun scoring.

Sex-prior wording is neutral and only appears when the sex component contributed. Explicit
priority suppression is not normally mentioned in prose.

## API and Authorization

The persisted `WorkoutPlan.decision_trace` remains the internal audit source. Normal workout-plan
responses will no longer include `decision_trace`.

The existing role-protected `/api/v1/coach/workout-reviews/{review_id}` response will add a typed
`template_selection` projection containing:

- the concise explanation;
- selected template slug;
- selected candidate component scores and total.

The projection is created from the stored trace. It does not expose rejected templates or the full
decision trace by default. Existing `require_coach` authorization protects the endpoint; frontend
hiding is not treated as authorization.

## Coach UI

`CoachWorkoutReviewPage` will show a compact `علت انتخاب برنامه` section above the editable day
cards. The explanation is visible by default. A native collapsed `جزئیات امتیازدهی` section shows
the selected slug and six score values. The normal workout page is unchanged.

## Compatibility and Failure Handling

Plans created before Phase 8 may not contain a template-selection trace. Their Coach projection is
`null`, and the UI omits the section. Dynamic fallback after a selected template fails remains
unchanged; the selection trace continues to describe only the structural selection decision.

## Verification

Focused backend tests cover trace completeness, score-object reuse, component totals, every reason
category, hard rejection separation, deterministic tie-breaks, duration exclusion, unchanged score
snapshots, trace-only explanation generation, member response privacy, and Coach authorization.

Focused frontend tests cover the Coach explanation and collapsed score details while proving the
member workout page does not render them. Existing Program Engine and workout-review regression
suites remain required.
