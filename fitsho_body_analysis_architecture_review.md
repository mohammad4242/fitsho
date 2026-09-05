# Fitsho Body Analysis — Proposed Product & Architecture for Review

## Purpose

This document describes a proposed redesign of Fitsho's **Body Analysis** feature.

It is intentionally a **design proposal, not an implementation plan**.

The goal is to give a senior planning/reasoning model enough context to:

1. inspect the existing repository,
2. challenge this proposal,
3. identify architectural risks,
4. suggest a better product or technical design if one exists,
5. and then propose the safest implementation approach.

The final user-facing explanation from the reviewing model should be written in **Persian**.

---

# 1. Product Goal

Body Analysis should feel like a useful, friendly fitness coach review rather than a long AI-generated checklist.

The user should understand, within roughly 30–60 seconds:

- what body-composition direction currently makes the most sense,
- what looks relatively strong,
- what areas may have the most room to improve,
- how balanced the physique appears,
- what changed compared with a previous scan,
- and whether the AI result has been reviewed by a human coach and physician.

The product should remain:

- visually simple,
- friendly,
- motivating without making false promises,
- non-diagnostic,
- conservative about uncertain image-based conclusions,
- stable enough that the schema and UI do not need redesign every few weeks.

---

# 2. Current Repository Context

The existing Body Analysis flow already includes:

- standardized front / side / back body photos,
- browser-side image processing,
- MediaPipe-based pose landmark detection,
- body segmentation,
- image quality checks,
- a provider preflight,
- a structured AI analysis response,
- normalized analysis storage,
- specialist review state,
- workout-engine integration,
- and previous-analysis comparison logic.

Important existing files include:

## Frontend

- `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- `frontend/src/features/bodyPhotos/processor.ts`
- `frontend/src/features/bodyPhotos/BodyProgressPage.tsx`
- `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.tsx`
- `frontend/src/features/bodyPhotos/BodyAnalysisResult.tsx`
- `frontend/src/features/bodyPhotos/BodyAreaMap.tsx`
- `frontend/src/features/bodyPhotos/ProgressComparison.tsx`
- `frontend/src/features/bodyPhotos/types.ts`
- `frontend/src/features/bodyPhotos/api.ts`
- `frontend/src/features/bodyPhotos/bodyPhotos.css`

Profile data is already available through files such as:

- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/ProfileContext.tsx`
- `frontend/src/features/profile/ProfilePage.tsx`
- `frontend/src/features/profile/OnboardingPage.tsx`

The profile already includes fields such as:

- sex,
- height,
- current weight,
- shoulder circumference,
- waist circumference,
- hip circumference,
- fitness goal.

## Backend

- `backend/app/body_analysis/service.py`
- `backend/app/body_analysis/schemas.py`
- `backend/app/body_analysis/normalization.py`
- `backend/app/body_analysis/api_schemas.py`
- `backend/app/body_analysis/router.py`
- `backend/app/body_analysis/runtime.py`
- `backend/app/body_analysis/models.py`

Comparison-related code already exists in:

- `backend/app/body_analysis/comparison_service.py`
- `backend/app/body_analysis/comparison_schemas.py`
- `backend/app/body_analysis/comparison_models.py`
- `backend/app/body_analysis/comparison_router.py`

Workout integration already exists in:

- `backend/app/workouts/body_analysis_resolver.py`
- `backend/app/workouts/program_engine/body_analysis.py`
- `backend/app/workouts/program_engine/engine.py`

Existing workout integration should remain as stable as possible.

---

# 3. Current Problem

The current result is too verbose and too checklist-oriented.

The existing model contract forces a large number of body-area findings and per-view outputs, which causes low-value text such as:

- "not assessable from the back,"
- "average,"
- "balanced,"
- repetitive evidence for areas that do not need explanation.

This creates a long report without giving the user a clear answer to the most important questions.

A second problem is that confidence is currently easy to misinterpret.

A numeric confidence score can look like "83% accuracy" to the user even when it is only an internal aggregation of finding-level confidence.

A third problem is that the UI exposes too much raw provider output instead of transforming structured evidence into a deliberate product experience.

---

# 4. Core Design Principle

The AI model should **not own the final UX copy**.

The model should primarily return structured observations.

Fitsho should own:

- final section structure,
- labels,
- friendly Persian tone,
- status colors,
- disclaimers,
- wording for coach/doctor review,
- empty-state behavior,
- and user-facing prioritization.

This reduces variability and makes the product more testable.

The AI may still return short free-text evidence when a visual explanation is genuinely useful.

---

# 5. Required Body Analysis Inputs

For Body Analysis specifically, the following should be required before analysis starts:

- height,
- weight,
- waist circumference,
- shoulder circumference,
- hip circumference,
- sex or a supported neutral handling path,
- front photo,
- side photo,
- back photo.

These measurements do not necessarily need to be mandatory for the entire Fitsho app.

They should be mandatory only when the user chooses to run Body Analysis.

The analysis should use:

- current profile goal,
- current measurements,
- current photos,
- previous scan measurements when available,
- previous scan findings when available.

---

# 6. Photo Capture Experience

The user should have two capture methods:

## Method A — Upload

The user can upload an existing image for each required view.

## Method B — Live Ghost Camera

Fitsho opens the camera inside the app and displays a ghost silhouette overlay.

Views:

- front,
- side,
- back.

The ghost should be intentionally tolerant.

This should be **loose alignment**, not a strict biometric scanner.

The user should only need to place the body approximately inside the frame.

The product should help with:

- distance,
- body framing,
- view correctness,
- lighting,
- visible full body,
- approximate alignment.

It should not block users for small alignment differences.

Existing MediaPipe landmarks and segmentation should be reused where appropriate.

Suggested new frontend components:

- `GhostCameraCapture.tsx`
- `GhostOverlayGuide.tsx`

Potential metadata worth storing or sending:

- capture method: `upload | live_ghost`
- view
- capture timestamp
- quality metadata
- optional alignment quality

Do not store unnecessary biometric data.

---

# 7. Proposed User-Facing Result

The result page should be intentionally short and layered.

## Section 1 — Friendly First Impression

This is the first thing the user sees.

The system recommends one high-level body-composition direction from a controlled set such as:

- weight loss,
- weight gain,
- fat loss,
- body recomposition,
- muscle hypertrophy / muscle gain.

Internally, it may be better to reuse existing goal enums such as `build_muscle` rather than introducing unnecessary duplicate concepts.

Example Persian UX intent:

> "به نظرم الان ریکامپ برای تو انتخاب بهتریه؛ چون با توجه به عکس‌ها، وزن، دور کمر و تناسب فعلی بدنت، می‌تونی همزمان روی پایین آوردن چربی و حفظ یا رشد عضله تمرکز کنی."

The tone should be:

- friendly,
- positive,
- Iranian/Persian-natural,
- not childish,
- not overly motivational,
- not medical,
- not absolute.

The model should never claim certainty from images alone.

---

# 8. Four Main Visual Indicators

The second section contains only four high-level indicators.

For male users:

1. V-taper
2. upper-body / lower-body balance
3. visible symmetry
4. bodybuilding potential / physique-development potential

For female users:

1. waist-to-hip proportion
2. upper-body / lower-body balance
3. visible symmetry
4. physique-development potential

Important concern for review:

"Bodybuilding potential" may be too scientifically strong if presented as a hard score.

The reviewer should decide whether this should instead be framed as something like:

- "physique development potential,"
- "visible structural potential,"
- "bodybuilding suitability,"
- or another safer and more meaningful concept.

Avoid false precision where possible.

A categorical scale may be better than a fake exact number:

- low,
- moderate,
- good,
- very good.

---

# 9. Main Interactive Body Map

This is the central visual element.

The current simple line-drawing body should be replaced with a higher-quality body illustration.

Desired assets:

- male front,
- male back,
- female front,
- female back,
- neutral fallback if necessary.

Style:

- fitness-oriented,
- clean,
- not photorealistic,
- not medical textbook style,
- not exaggerated bodybuilding proportions.

Muscle regions should be interactive.

When the user taps a body area:

- that region becomes visually highlighted,
- a short insight appears.

Example positive insight:

> "چی ساختی! چهارسرها نسبت به بقیه پایین‌تنه خوب جلو افتادن."

Example growth insight:

> "سرشونه‌هات نسبت به بازو و عرض بالاتنه کمی عقب‌تر دیده می‌شن؛ اینجا می‌تونه یکی از بهترین نقاط تمرکزت باشه."

Below the map:

- 🟢 stronger
- ⚪ balanced
- 🟠 room to grow
- 🔴 primary priority

Example:

- 🟢 stronger: quads, chest
- ⚪ balanced: arms, calves, midsection
- 🟠 room to grow: lats
- 🔴 primary priority: lateral delts

The body map should not display meaningless confidence percentages next to every muscle.

Confidence should be used mostly for internal gating and uncertainty behavior.

---

# 10. Human Review Status

After the body map, show a very clear AI limitation message.

Suggested product copy intent:

> "یادت باشه من هوش مصنوعی‌ام و ممکنه اشتباه کنم. برای اطمینان بهتره این تحلیل به تأیید مربی و پزشک برسه."

Below it:

- Coach review — red indicator until approved, green after approval
- Physician review — red indicator until approved, green after approval

The repository already has specialist review state.

This UI should reuse the existing review model instead of creating a parallel approval system.

The disclaimer should be product-owned static copy, not generated differently on each AI run.

---

# 11. "My Body Over Time"

This section appears when the user has previous valid analyses.

The goal is to make repeated body scans meaningful.

Each scan should have:

- date,
- time,
- linked photo session,
- measurements,
- analysis version.

The UI should feel like a timeline or connected series.

Example:

### Compared with 32 days ago

- 🟢 shoulders: visible improvement
- 🟢 waist: 2 cm smaller
- ➖ legs: approximately stable
- 🟠 lats: still the main growth area

Changes should also be highlighted on the body illustration where useful.

A before/after image slider should be available.

The comparison should use both:

- structured analysis change,
- actual stored measurement change.

Do not let image-only AI comparison override reliable numeric measurement data.

---

# 12. Comparison Architecture

The repository already includes deterministic comparison logic.

The proposed redesign should reuse and improve that system rather than introducing an unrelated second comparison pipeline.

Important design question for review:

Should "change over time" be generated from:

### Option A
Only normalized classifications.

### Option B
Measurements + normalized classifications.

### Option C
A dedicated visual comparison AI call that receives both old and new standardized photo sets, plus measurements.

Current preference:

Use **measurements + normalized classifications as the stable base**, and only use direct visual comparison if it provides enough additional value to justify the added cost, complexity, and uncertainty.

The reviewing model should evaluate this carefully.

---

# 13. AI Output Contract

The model should return structured information.

Possible conceptual fields:

```text
assessment_status

goal_recommendation
  suggested_goal
  reasons
  confidence

physique_indicators
  taper_or_waist_hip
  upper_lower_balance
  visible_symmetry
  physique_development_potential

body_areas[]
  area
  classification
  evidence
  supporting_views
  confidence
  suggested_training_emphasis

summary
  strongest_areas
  growth_areas
  primary_priority
  uncertain_areas
```

The exact schema should be reviewed before implementation.

Do not blindly keep the current v3 structure if a cleaner v4 contract would reduce complexity.

However, preserve backward compatibility for old persisted analyses.

---

# 14. Stable Internal Contract for Workout Personalization

The workout engine should continue consuming a narrow internal contract.

The UI redesign must not make the workout engine depend on presentation-specific fields.

The stable concepts should remain similar to:

- body area,
- classification,
- confidence,
- severity,
- suggested training emphasis.

The following files should be touched as little as possible:

- `backend/app/workouts/body_analysis_resolver.py`
- `backend/app/workouts/program_engine/body_analysis.py`
- `backend/app/workouts/program_engine/engine.py`

If the reviewer finds a reason these must change, it should explain why.

---

# 15. Goal Recommendation Safety

The AI should not diagnose or prescribe.

It may make a fitness-oriented advisory recommendation using:

- current goal,
- height,
- weight,
- BMI,
- waist circumference,
- shoulder circumference,
- hip circumference,
- visible physique proportions,
- previous trend when available.

It should not:

- estimate medical risk,
- diagnose obesity or disease,
- infer injury,
- estimate precise body-fat percentage without a validated dedicated model,
- make claims about genetics,
- promise future physique outcomes.

Instead of:

> "You have great genetics for bodybuilding."

Prefer:

> "Your current visible proportions suggest that adding shoulder and lat development could noticeably improve your overall silhouette."

---

# 16. Profile and Measurement Requirements

Existing profile fields already contain:

- `height_cm`
- `current_weight_kg`
- `shoulder_circumference_cm`
- `waist_circumference_cm`
- `hip_circumference_cm`
- `sex`
- `fitness_goal`

The redesign should first determine whether these are already stored in the best source of truth.

Avoid duplicating measurements inside Body Analysis tables if the profile/body-measurement history already solves this.

Body Analysis should snapshot the measurement values used for each analysis if reproducibility requires it.

The reviewer should inspect whether a snapshot already exists or should be added.

---

# 17. Likely Frontend Changes

Expected significant changes:

- `BodyPhotoWizard.tsx`
- `processor.ts`
- `BodyAnalysisResultPage.tsx`
- `BodyAnalysisResult.tsx`
- `BodyAreaMap.tsx`
- `ProgressComparison.tsx`
- `types.ts`
- `bodyPhotos.css`

Likely new components:

- `GhostCameraCapture.tsx`
- `GhostOverlayGuide.tsx`
- `BodyAnalysisHero.tsx`
- `BodyMetricsCards.tsx`
- `BodyAreaInsightPanel.tsx`
- `ApprovalStatusCard.tsx`
- `BodyTimeline.tsx`
- `BeforeAfterSlider.tsx`

The reviewer should challenge this split.

Do not create components only for organizational aesthetics.

Create them only when they represent a real responsibility boundary.

---

# 18. Likely Backend Changes

Expected significant changes:

- `backend/app/body_analysis/service.py`
- `backend/app/body_analysis/schemas.py`
- `backend/app/body_analysis/normalization.py`

Expected moderate changes:

- `backend/app/body_analysis/runtime.py`
- `backend/app/body_analysis/api_schemas.py`
- `backend/app/body_analysis/router.py`
- comparison service/schemas if needed

Likely minimal or no database model changes:

- `backend/app/body_analysis/models.py`

The reviewer should verify whether a migration is actually needed.

Prefer no schema migration unless there is a real persistence requirement that JSON result storage cannot safely handle.

---

# 19. Prompt Versioning

If the model response contract changes materially, do not silently modify v3.

Prefer explicit versioning, for example:

- prompt version: `body-analysis-v4`
- schema version: `4.0`

Old v1/v2/v3 analyses should remain readable.

Normalization should preserve compatibility with the stable internal workout contract.

---

# 20. Tests That Will Probably Need Review

Backend:

- `backend/tests/body_analysis/test_normalization.py`
- `backend/tests/body_analysis/test_execution_and_reviews.py`
- `backend/tests/body_analysis/test_progress_comparison.py`
- `backend/tests/e2e/test_body_analysis_agent_service.py`
- `backend/tests/admin/test_ai_task_smoke.py`

Agent-service:

- `agent-service/tests/test_task_prompt_ownership.py`

Frontend:

- `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
- `frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx`
- `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx`
- `frontend/src/features/bodyPhotos/api.test.ts`

New focused tests should be added only where new behavior exists.

Do not preserve old tests merely because they existed.

Update tests when the intended product contract changes.

---

# 21. Product Behavior for Missing or Weak Data

The design should avoid showing empty decorative sections.

Examples:

- If there is no meaningful strength, do not show an empty "strengths" card.
- If no previous scan exists, do not show comparison UI.
- If an area cannot be assessed, do not create three repetitive "not assessable" messages.
- If one photo is weak but two views are still usable, the system may produce a partial analysis if the existing safety rules allow it.
- If the core measurements are missing, Body Analysis should not start.

---

# 22. Language and Tone

The backend model may generate short Persian evidence.

The final product language should sound like a capable Iranian fitness coach.

Desired characteristics:

- conversational,
- concise,
- supportive,
- specific,
- not fake-friendly,
- not robotic,
- not overly formal,
- no motivational filler.

Bad:

> "با تلاش و پشتکار قطعاً به بهترین نسخه خودت تبدیل خواهی شد."

Better:

> "بالاتنه‌ات نسبتاً متعادله؛ بیشترین جای رشد فعلاً سرشونه و لت دیده می‌شه."

Positive feedback is welcome when evidence exists.

Example:

> "چهارسرها خوب جلو افتادن؛ فعلاً جزو اولویت‌های اصلی رشد نیستن."

---

# 23. Important Open Questions for the Reviewer

Please inspect the repository and answer these before implementation:

1. Is this product structure better than the current Body Analysis architecture?
2. Would you keep the existing 13-area normalized contract?
3. Should the provider schema become v4?
4. Should the friendly opening be generated by the model, Fitsho templates, or a hybrid?
5. Is "bodybuilding potential" a useful/safe concept, or should it be renamed/replaced?
6. Are shoulder/waist/hip measurements stored in the correct place already?
7. Should those measurements be snapshotted with each analysis?
8. Is a true in-app `getUserMedia` Ghost Camera worth the complexity?
9. Can the current MediaPipe pipeline support loose live alignment cleanly?
10. Should upload and live capture feed the exact same processing pipeline?
11. Should timeline comparison use the existing `comparison_service.py` or a new higher-level presentation service?
12. Is direct old-photo/new-photo AI comparison worth adding?
13. Can the redesign avoid a database migration?
14. Which current files should definitely not be touched?
15. Which existing abstractions are already good and should be preserved?
16. Which parts of this proposal are over-engineered?
17. Which parts are missing?
18. What is the smallest architecture that still gives the desired premium UX?
19. What should be implemented now versus deferred?
20. How should backward compatibility with existing v1/v2/v3 results work?

---

# 24. Success Criteria

A successful redesign should satisfy all of the following:

- The first screen of the result gives a useful conclusion.
- The user understands the recommended direction.
- The report is much shorter than the current one.
- The body map is the main visual interaction.
- Repeated per-view boilerplate disappears.
- Strengths and priorities are obvious.
- AI uncertainty is visible without dominating the UX.
- Coach/doctor review status is clear.
- Repeated scans become more valuable over time.
- The workout engine remains stable.
- Existing stored analyses remain readable.
- The implementation does not introduce unnecessary schema or database complexity.
- Future prompt/model improvements should not require redesigning the UI.

---

# 25. Review Instruction

Do **not** assume this proposal is correct.

Inspect the repository first.

If you find a better product architecture or a simpler technical design, propose it.

When proposing changes:

- explain the reasoning,
- identify exact files,
- distinguish required changes from optional enhancements,
- preserve stable boundaries where possible,
- identify migration/backward-compatibility risks,
- and avoid unrelated refactors.

Before implementation, return a reviewed design and implementation plan.

Explain the final findings to the user in **Persian**.
