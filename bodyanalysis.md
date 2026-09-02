# Fitsho Body Analysis v4 — Architecture Decision and Implementation Roadmap

> Delivery note: This document is ready to be saved as `bodyanalysis.md`. The current session is in Plan Mode, so no repository file was created or modified.

## 1. Overall Assessment

The proposed product direction is strong, but the architecture document must not be implemented as written.

The recommended design is:

- Create a new evidence-only provider contract: Body Analysis v4.
- Keep v1, v2, and v3 immutable for backward compatibility.
- Remove the 13 areas × 3 views user-facing checklist.
- Keep the existing normalized 13-area contract exclusively as a compatibility adapter for workout generation.
- Make the vision LLM responsible only for structured visual observations.
- Generate all first impressions, indicator labels, goal direction, disclaimers, and Persian UI copy through deterministic Fitsho code.
- Store an immutable measurement/profile snapshot without creating new database tables.
- Reuse the existing review, comparison, photo storage, and workout-engine boundaries.
- Add the Ghost Camera as a new input method while preserving the existing upload processing pipeline.
- Build My Body Over Time from deterministic measurement and normalized-analysis comparisons. Do not add a second comparison LLM call.

This architecture is recommended over either simplifying v3 in place or limiting the redesign to frontend presentation.

## 2. Problems Found in the Proposed Architecture and Current Product

### Current v3 contract

The current contract forces:

- Exactly 13 findings.
- A front, side, and back checklist for every finding.
- Repetitive Persian evidence for all 39 area/view combinations.
- LLM-generated first impression and goal reasoning.
- Numeric confidence values presented as percentages.

This creates excessive output, repetitive UI, higher token cost, and false precision.

### Provider ownership is too broad

The provider currently owns user-facing Persian prose and goal recommendation. This makes tone, terminology, safety, and product consistency model-dependent.

### Measurement reproducibility is missing

`BodyMeasurement` is already the correct append-only source of truth. However, the analysis service reads the latest measurement only when the asynchronous AI execution starts. A profile update between queueing and execution can change the analysis inputs.

### Current history has two competing implementations

- The backend already persists owner-scoped deterministic comparisons.
- The frontend independently recalculates comparisons in `comparison.ts`.
- The result page fetches prior sessions and analyses through an N+1 request loop instead of using the stored comparison endpoint.

### Current visual product is misleading

`frontend/public/body-analysis/Bod.png` is:

- Male-only.
- Extremely muscular.
- Decorated with unsupported body-fat, muscle-mass, BMI, and proportion metrics.
- Unsuitable as a neutral Body Analysis product illustration.

### “Bodybuilding potential” is not defensible

A standardized photo cannot reliably estimate:

- Genetics.
- Future hypertrophy response.
- Competitive potential.
- Long-term muscular ceiling.

Remove this indicator entirely.

### V-taper and waist-to-hip labels require care

Shoulder circumference is not the same measurement as visual shoulder breadth or V-taper. Waist-to-hip ratio is also sensitive to measurement technique. Self-measurement can be useful, but only with standardized instructions and without presenting an ideal or health score. A study of self-measured circumferences confirms that protocol and technique materially affect reliability: [self-measured circumference reliability study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4855335/).

### Current medical-claim protection is incomplete

The current banned-claim regex is English-focused while provider prose is Persian. V4 should remove free-form provider prose and structurally prohibit medical, genetic, body-fat, pain, diagnosis, and posture claims.

## 3. Better Product Architecture

Three realistic approaches exist:

1. Keep and simplify v3.
2. Create evidence-only v4 — Recommended.
3. Keep backend contracts and redesign only the frontend.

The recommended architecture has four separate contracts:

1. **Provider evidence contract**
   - AI-owned.
   - Stored privately in `raw_result`.
   - Never rendered directly.

2. **Normalized compatibility contract**
   - Fitsho-owned.
   - Persisted and versioned.
   - Remains compatible with the workout engine and specialist corrections.

3. **Experience read model**
   - Fitsho-owned and generated deterministically.
   - Returned through the API for v4.
   - Contains presentation keys, parameters, indicators, map regions, review state, and snapshot provenance.
   - Not persisted as a second source of truth.

4. **Historical comparison contract**
   - Deterministic.
   - Combines exact measurement changes with normalized-analysis changes.
   - Clearly labels the provenance of every statement.

## 4. Final Recommended Architecture

### Authoritative data ownership

| Concern | Authority |
|---|---|
| Height, sex, selected goal | `UserProfile` |
| Weight and circumferences | Latest `BodyMeasurement` |
| Analysis-time reproducibility | Immutable snapshot inside `BodyAnalysis.raw_result` |
| Photo files and consent | Existing `body_photos` module |
| Browser framing and pose guidance | MediaPipe plus deterministic frontend logic |
| Visual evidence | Vision LLM v4 provider payload |
| Product classifications and Persian wording | Fitsho backend/frontend |
| Specialist corrections | Existing `BodyAnalysisResultVersion` |
| Coach and physician approval | Existing `BodyAnalysisReview` |
| Workout influence | Existing normalized contract and resolver |
| Historical measurement deltas | Deterministic backend |
| Historical visual changes | Deterministic normalized-result comparison |

### Database decision

No database migration is required.

Use the existing JSON fields:

- `BodyAnalysis.raw_result`
- `BodyAnalysis.normalized_result`
- `BodyAnalysisResultVersion.normalized_result`
- `BodyProgressComparison.normalized_result`
- `BodyProgressComparison.context_snapshot`

Do not duplicate profile or measurement values in a new table.

## 5. Complete Data Flow

1. The wizard reads the authenticated profile through the existing `ProfileContext`.
2. It verifies:
   - Sex is present; `other` and `prefer_not_to_say` are valid neutral values.
   - Height is present.
   - Weight is present.
   - Shoulder circumference is present.
   - Waist circumference is present.
   - Hip circumference is present.
   - A fitness goal is present.
3. Missing or stale-looking values are edited through the existing profile PATCH API.
4. The user explicitly confirms that the displayed measurements represent the current scan.
5. The user selects upload or Ghost Camera for each front, side, and back photo.
6. Both paths produce a browser `File`.
7. Both paths call the existing `BrowserBodyPhotoProcessor.process(file, view)`.
8. The processor performs deterministic format, dimensions, quality, pose, framing, view-family, segmentation, and background normalization.
9. A failed local validation keeps the user on the current photo step and requires a retake or reselection.
10. The existing private upload API stores each processed photo only after local validation succeeds.
11. Session submission records the existing operational and optional training consents.
12. `POST /api/v1/body-photo-sessions/{session_id}/analysis` receives:
    ```json
    {
      "confirm_measurements_current": true
    }
    ```
13. In the same queue transaction, the backend validates required fields and captures an immutable input snapshot.
14. Analysis starts only when all three browser-approved standardized photos exist: front, side, and back.
15. The vision model receives all three accepted images and view labels in one v4 evidence-only request. It does not receive sex, goal, BMI, or measurements.
16. The provider returns structured v4 visual evidence with no final message or goal recommendation.
17. Fitsho validates the evidence and projects it into the existing normalized 13-area contract.
18. The normalized result is persisted as result version 1.
19. The deterministic comparison service creates or updates the stored comparison. Comparison failure remains non-blocking.
20. The API assembles a v4 experience read model from:
    - The current effective normalized result.
    - The immutable input snapshot.
    - Validated provider evidence.
    - Current specialist-review state.
21. The frontend renders the first impression, indicators, body map, sparse insights, and review states.
22. The workout resolver reads only the normalized result and remains isolated from all presentation changes.

Photo acceptance belongs to the local/browser processing flow. The vision model is called only once, for Body Analysis itself.

## 6. Exact Responsibility Boundaries

### A. Deterministic Fitsho code

Fitsho owns:

- Required-field validation.
- Snapshot creation.
- BMI and circumference-ratio calculation on demand.
- Goal-direction policy.
- V4-to-normalized projection.
- Evidence-strength downgrading.
- Allowed area-to-training-emphasis mapping.
- First-impression selection.
- Persian presentation keys and parameters.
- Four indicator construction.
- Body-map region classification.
- Review-state presentation.
- Measurement deltas.
- Historical visual-state transitions.
- Disclaimer text.
- Backward-compatible response assembly.

Fitsho must never claim that a compatibility score is a probability of correctness.

### B. MediaPipe

MediaPipe owns only browser-local assistance:

- Person count.
- Pose landmarks.
- Body-in-frame guidance.
- Approximate distance/framing.
- Approximate side versus non-side guidance.
- Captured-image segmentation and gray-background normalization.

MediaPipe must not:

- Diagnose posture.
- Identify the user.
- Infer sex.
- Infer body composition.
- Determine front versus back with hard certainty.
- Generate workout priorities.

### C. Vision LLM

The vision model owns:

- Relative visual development observations.
- Upper/lower visible balance.
- Visible image-left/image-right difference.
- Supporting-view selection.
- Controlled limitation and observation tags.
- Controlled training-emphasis candidates.

The vision model does not accept or reject photos, make photo-quality decisions, or decide whether a scan is usable. It evaluates body observations in the three standardized images after local acceptance.

It must not generate:

- Friendly final messages.
- Goal recommendations.
- BMI interpretation.
- Body-fat estimates.
- Medical or postural findings.
- Genetic or bodybuilding-potential claims.
- Exercise prescriptions.
- Numeric user-facing confidence percentages.

### D. Workout engine

The workout engine consumes only:

- Normalized lag classifications.
- Allowed training emphases.
- Internal compatibility evidence scores.
- Result provenance and version.

No v4 experience, body-map, camera, timeline, indicator, or Persian-presentation type may enter the engine.

### E. Comparison system

The comparison system owns:

- Measurement deltas from exact snapshots.
- Visual classification transitions from normalized results.
- Persistent priorities.
- Date interval.
- Provenance labels.
- Before/after session selection.

It does not compare raw pixels and does not call another LLM.

## 7. Proposed Body Analysis Output Contracts

### 7.1 Provider evidence v4

Add `BodyAnalysisEvidenceV4Payload` with `extra="forbid"` and strict validation.

```text
schema_version: "4.0"
assessment_status: complete | partial
  (legacy compatibility; new executions must return complete)

area_observations: exactly 11 entries
  area:
    shoulders
    chest
    back
    lats
    arms
    forearms
    waist_midsection
    glutes
    quads
    hamstrings
    calves

  classification:
    stronger
    balanced
    room_to_grow
    primary_priority
    not_assessable

  evidence_strength:
    low
    moderate
    high

  supporting_views:
    unique subset of front | side | back

  observation_tags:
    relative_width
    relative_thickness
    relative_prominence
    side_profile
    left_right_difference
    visibility_limited

  limitation_codes:
    controlled existing visibility/pose/lighting/occlusion values

  suggested_training_emphasis:
    controlled existing visual emphasis values

upper_lower_balance:
  state:
    upper_body_dominant
    lower_body_dominant
    balanced
    uncertain
  evidence_strength
  supporting_views

visible_symmetry:
  state:
    no_clear_difference
    minor_visible_difference
    clear_visible_difference
    uncertain
  evidence_strength
  supporting_views
```

No provider field may contain free-form Persian prose.

### 7.2 Evidence projection

Map v4 classifications as follows:

| V4 evidence | Normalized classification |
|---|---|
| `stronger`, high | `strength` |
| `stronger`, moderate | `neutral` |
| `balanced`, moderate/high | `neutral` |
| `room_to_grow`, high/moderate | `mild_lag` |
| `primary_priority`, high | `clear_lag` |
| `primary_priority`, moderate | `mild_lag` |
| Low evidence | `uncertain` |
| `not_assessable` | `uncertain` |

Internal compatibility scores:

| Evidence strength | Internal score |
|---|---:|
| Low | 0.40 |
| Moderate | 0.65 |
| High | 0.85 |

These values are routing thresholds, not probability estimates. They must never be shown to users.

The backend caps high evidence to moderate when the submitted supporting views are insufficient for the relevant area.

Project the 13 normalized areas as follows:

- Eleven anatomical areas come from `area_observations`.
- `symmetry` comes from `visible_symmetry`.
- `visible_alignment_or_posture` is always `uncertain`, has no training emphasis, and receives a visibility limitation. V4 intentionally does not collect posture findings.

For new complete v4 executions, normalized overall compatibility confidence uses the deterministic internal ceiling `0.85`. The legacy `partial` literal remains only for backward-compatible stored payloads; new execution does not create a partial analysis path.

### 7.3 Experience read model

Add `BodyAnalysisExperienceV4` to the API response:

```text
schema_version: "4.0"
presentation_version: "body-analysis-experience-v1"
assessment_status: complete | partial

input_snapshot:
  captured_at
  confirmed_at
  profile_updated_at
  measurement_id
  measurement_measured_at
  sex
  height_cm
  weight_kg
  shoulder_circumference_cm
  waist_circumference_cm
  hip_circumference_cm
  selected_goal

first_impression:
  message_key
  parameters

direction:
  status:
    aligned_with_current_goal
    goal_confirmation_required
  goal: existing FitnessGoal or null
  reason_codes

indicators:
  body_proportion
  upper_lower_balance
  visible_symmetry
  current_development_focus

regions:
  area
  display_classification
  insight_key or null
  insight_parameters
  supporting_views

review_notice_code
```

The response assembler must derive region state from the current result version’s normalized result. This ensures specialist corrections immediately update the body map.

### 7.4 Legacy visual result

- Keep `visual_result` for v2 and v3 responses.
- For v4, return `visual_result: null`.
- Return `experience_result` only for v4.
- Never expose `raw_result`.

## 8. Ghost Camera Design

### Privacy rule

Preserve the established no-face architecture:

- Do not add face detection.
- Do not add automatic face tracking.
- Show a visible privacy cut line in the overlay.
- The user positions the neck/shoulder line below that cut.
- Crop the captured canvas at that fixed user-visible boundary.
- Live frames remain inside the browser and are never uploaded.
- Upload only the confirmed, headless, processed JPEG.

### Camera behavior

Use:

```text
navigator.mediaDevices.getUserMedia({
  audio: false,
  video: {
    facingMode: { ideal: "user" },
    width: { ideal: 1280 },
    height: { ideal: 1920 }
  }
})
```

Provide:

- Front/environment camera toggle when available.
- Five-second timer.
- Front, side, and back view-specific silhouette.
- Retake and confirm actions.
- Stream cleanup on close, route change, unmount, error, and page visibility loss.
- Upload fallback for denied permission, unsupported browser, insecure context, or camera failure.

`getUserMedia` requires the correct browser permission and secure deployment context. Camera data is sensitive and requires explicit consent under the media-capture specification: [W3C Media Capture](https://www.w3.org/TR/mediacapture-streams/).

### Live checks

Run only lightweight pose guidance live:

- At most one foreground person.
- Shoulders-to-feet inside the guide.
- Person too close or too far.
- Approximate side/non-side view.
- Basic lighting warning.
- Phone orientation warning.

Live checks are advisory. The capture button remains available.

Do not run segmentation live.

The existing web Pose Landmarker uses `IMAGE` mode. Live guidance needs a separate `VIDEO`-mode instance and `detectForVideo`. The API is synchronous and can block the main thread, so throttle to approximately 4–6 low-resolution checks per second and disable live pose guidance on slow devices while preserving the silhouette overlay. See the official [MediaPipe Web Pose Landmarker guide](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/web_js).

### Shared post-capture pipeline

After capture:

1. Draw the selected video frame to canvas.
2. Apply the same preview/capture mirroring transform consistently.
3. Remove the region above the visible privacy cut.
4. Export a JPEG `File`.
5. Pass it to `BrowserBodyPhotoProcessor.process(file, view)`.
6. Use existing validation, segmentation, gray background, and upload code.

Upload and camera capture must never diverge after file acquisition.

## 9. Interactive Body Map Design

Use semantic inline SVG regions.

Do not use raster masks or coordinate dots.

Required illustrations:

- Male front.
- Male back.
- Female front.
- Female back.
- Neutral front.
- Neutral back.

All six assets must share:

- The same viewBox.
- Stable anatomical region IDs.
- Separate illustration paths and interactive hit paths.
- Original or properly licensed artwork.

Variant selection:

| Profile sex | Map variant |
|---|---|
| `male` | Male |
| `female` | Female |
| `other` | Neutral |
| `prefer_not_to_say` | Neutral |
| Missing legacy value | Neutral |

Interactive regions cover the eleven anatomical v4 areas. Symmetry and upper/lower balance remain indicator cards, not body regions.

Classification colors:

- Stronger: green.
- Balanced: neutral gray.
- Room to grow: amber.
- Primary priority: red.
- Not assessable: muted outline.

Color must not be the only cue. Add outline, pattern, icon, and text labels.

Interaction requirements:

- Tap/click selection.
- Keyboard selection.
- Visible focus.
- `aria-pressed`.
- Front/back switch.
- Selected-region short insight.
- Highlight all paths belonging to the selected region.
- No confidence percentage.
- No prose for irrelevant balanced regions.
- Specialist-corrected normalized classifications take precedence over AI evidence.

## 10. My Body Over Time

### Data authority

Use one deterministic timeline read model.

For each comparison, output:

- Previous and current session dates.
- Exact interval in days.
- Exact recorded measurement deltas.
- Visual observation transitions.
- Current persistent priorities.
- Review state.
- Before/after protected photo URLs.
- Provenance for every item.

### Trust labels

Measurement statement:

> Waist: 84 cm → 82 cm, change −2 cm.

Label as:

> Based on measurements recorded by you.

Visual statement:

> The standardized visual assessment of the shoulders changed from balanced to stronger.

Label as:

> Visual observation from standardized photos; not a direct muscle-size measurement.

Persistent priority:

> Lats remain a primary priority in both analyses.

### No additional AI comparison

Do not add old-photo/new-photo LLM comparison in the first implementation.

The existing normalized results already contain enough structured visual evidence. A second AI call would increase cost and inconsistency without providing measurement-grade truth.

### Timeline API

Add:

```text
GET /api/v1/body-progress/timeline
```

The endpoint returns a single owner-scoped read model containing sessions, analyses, snapshots, comparisons, photos, and review state. It replaces frontend N+1 analysis discovery.

Keep the existing endpoint:

```text
GET /api/v1/body-photo-sessions/{session_id}/comparison
```

### Before/after slider

- Default to front view.
- Allow front/side/back switching.
- Use the existing authenticated `content_url`.
- Support keyboard control.
- Display dates and view names.
- Never imply automated pixel measurement.

## 11. Backward Compatibility with v1/v2/v3

- Do not update existing database rows.
- Do not backfill v4 payloads.
- Do not reinterpret v1/v2/v3 provider payloads as v4.
- Keep current v1, v2, and v3 Pydantic types and normalizers.
- Add v4 as a new explicit branch.
- Keep legacy `visual_result` rendering for v2/v3.
- Render v1 using normalized legacy presentation.
- Render v4 through `experience_result`.
- Existing specialist reviews and result versions remain valid.
- Existing v1 comparisons remain readable.
- New v4 comparisons use comparison schema v2.
- Do not guess an exact historical measurement snapshot for legacy scans.
- If an old scan has exact workout-cycle measurement links, use them.
- Otherwise show measurement provenance as unavailable.
- Never silently pair an arbitrary nearby measurement with an old analysis.

## 12. Exact File-by-File Impact Map

### Backend: MUST CHANGE

| File | Current behavior | Required change | Dependencies | Risk |
|---|---|---|---|---|
| `backend/app/body_analysis/schemas.py` | Defines v1 normalized, v2 visual, and v3 13×3 checklist contracts. | Add evidence-only v4 schema and strict validators. Preserve all legacy models unchanged. | Service, normalizer, provider strict schema. | High: schema rejection or accidental legacy breakage. |
| `backend/app/body_analysis/normalization.py` | Validates legacy prose and projects v2/v3 into normalized results. | Add v4 evidence validation and deterministic 13-area projection. Keep legacy paths untouched. | Workout resolver and comparison. | High: incorrect workout priorities. |
| `backend/app/body_analysis/service.py` | Reads latest profile during AI execution, prompts v3, overwrites `raw_result`, and persists v3 visual output. | Capture snapshot during queue, reuse it during execution, merge raw JSON safely, call v4 provider schema, persist normalized v4, and leave v4 `visual_result` null. Retry without photo changes reuses the original snapshot; changed photos require a new confirmation and snapshot. | Profile models, provider, comparison. | High: race conditions and persistence compatibility. |
| `backend/app/body_analysis/runtime.py` | Hardcodes `body-analysis-v3` and schema `3.0`. | Change new executions to prompt `body-analysis-v4-evidence` and schema `4.0`. | Admin task configuration remains unchanged. | Medium: all new production analyses switch contract. |
| `backend/app/body_analysis/api_schemas.py` | Returns normalized plus v2/v3 visual results. | Add `BodyAnalysisStartRequest`, `BodyAnalysisExperienceV4`, `experience_result`, and legacy-safe unions. | Router and frontend types. | High: API compatibility. |
| `backend/app/body_analysis/router.py` | Starts analysis without a body and assembles legacy responses. | Accept measurement confirmation, return structured missing-field errors, and assemble deterministic v4 experience from the effective result version. | Service and presentation module. | High: current client start flow changes. |
| `backend/app/body_analysis/comparison_schemas.py` | Defines comparison schema v1 and workout-feedback context. | Add comparison v2 with exact measurement deltas, visual changes, persistent priorities, and provenance. Preserve v1. | Comparison service and history. | Medium. |
| `backend/app/body_analysis/comparison_service.py` | Compares normalized classifications and creates English boilerplate. | Add v4 snapshot-aware comparison v2 and controlled semantic reason codes. Preserve creation idempotency and non-blocking behavior. | Raw snapshots and normalized versions. | High: historical correctness. |
| `backend/app/main.py` | Registers the existing analysis and comparison routers. | Register the new owner-scoped history router only. Do not change middleware or unrelated routes. | New history router. | Low. |

### Backend: NEW FILES

| File | Responsibility | Dependencies | Risk |
|---|---|---|---|
| `backend/app/body_analysis/presentation.py` | Deterministic first impression, goal direction, indicators, map region state, insight keys, and experience assembly. | Normalized result, snapshot, review state. | Medium: product wording and correction consistency. |
| `backend/app/body_analysis/history_service.py` | Query sessions, analyses, snapshots, photos, review states, and stored comparisons without frontend N+1 calls. | Existing models only. | Medium: ownership and query performance. |
| `backend/app/body_analysis/history_schemas.py` | Timeline, scan card, comparison provenance, and before/after API models. | History service. | Low. |
| `backend/app/body_analysis/history_router.py` | Expose `GET /api/v1/body-progress/timeline`. | History service and authentication. | Low. |

### Backend: SHOULD REMAIN UNCHANGED

| File or subsystem | Why it must remain unchanged | Regression risk if changed |
|---|---|---|
| `backend/app/body_analysis/models.py` | Existing JSON and version tables already support v4. | Unnecessary migration and stored-result risk. |
| `backend/app/body_analysis/comparison_models.py` | Existing JSON columns support comparison v2. | Historical comparison corruption. |
| `backend/app/body_analysis/enums.py` | Existing 13 areas and training emphases are the engine compatibility contract. V4 provider literals belong in `schemas.py`. | Engine and stored-result breakage. |
| `backend/app/body_analysis/providers/openrouter.py` | Already provides generic strict structured image transport. | Provider-wide regression. |
| `backend/app/body_analysis/providers/agent_service.py` | Already transports Fitsho-owned prompt/schema to Agent Service. | Agent routing regression. |
| `backend/app/body_analysis/admin_config/*` | Provider/model/task configuration remains generic. | Admin and other AI tasks. |
| `backend/app/body_photos/models.py` | Session, photo, consent, and private storage structures are sufficient. | Privacy and migration risk. |
| `backend/app/body_photos/schemas.py` | Camera capture produces the same uploaded file contract. | Duplicate camera-specific backend contract. |
| `backend/app/body_photos/service.py` | Existing owner, consent, resume, delete, and private-storage behavior is correct. | Data-loss/privacy risk. |
| `backend/app/body_photos/router.py` | Existing upload/session API is reusable. | Route compatibility. |
| `backend/app/body_photos/image_validation.py` | Server format/signature/dimension validation remains required. | Security regression. |
| `backend/app/body_photos/storage.py` | Private storage must remain unchanged. | Photo exposure/data loss. |
| `backend/app/profile/models.py` | `UserProfile` and append-only `BodyMeasurement` are already authoritative. | Duplicate source of truth. |
| `backend/app/profile/service.py` | Existing updates append a measurement when values change. Identical confirmed values need only a new snapshot confirmation time. | Profile-wide regression. |
| `backend/app/profile/schemas.py` | Existing measurement fields and ranges are sufficient. | Public profile compatibility. |
| `backend/app/profile/enums.py` | Existing `FitnessGoal` and `Sex` values cover the product. | Database enum/check constraints. |
| `backend/app/workouts/body_analysis_resolver.py` | Correctly isolates normalized lag evidence from presentation. | Workout behavior drift. |
| `backend/app/workouts/program_engine/body_analysis.py` | Existing confidence and provenance gates remain valid through the v4 adapter. | Safety and prioritization drift. |
| `backend/app/workouts/program_engine/engine.py` | Must remain unaware of v4 presentation. | Large engine regression. |
| `backend/app/workouts/program_engine/*` | No camera, map, UI, or provider concepts belong here. | Broad unrelated changes. |
| `backend/app/workout_cycles/body_progress_service.py` | Existing cycle-level exact measurement and analysis comparison remains valid. | Cycle completion regression. |
| `backend/app/workout_cycles/models.py` | Existing cycle comparison persistence remains valid. | Migration risk. |
| `backend/app/workout_cycles/schemas.py` | Existing cycle API remains separate from the global timeline read model. | API breakage. |
| `backend/app/workout_cycles/router.py` | No new global timeline route should be added here. | Coupling cycle and global history. |
| `agent-service/app/*` | Agent Service must remain task-agnostic. | Cross-task coupling. |
| Existing Alembic migrations | No migration is required. | Unsafe historical rewriting. |

### Frontend: MUST CHANGE

| File | Current behavior | Required change | Dependencies | Risk |
|---|---|---|---|---|
| `frontend/src/features/bodyPhotos/types.ts` | Models v1/v2/v3, numeric confidence, and client comparison types. | Add v4 experience, snapshot, region, indicator, history, and comparison v2 types. Preserve legacy types. | API and all body-photo UI. | High. |
| `frontend/src/features/bodyPhotos/api.ts` | Starts analysis without confirmation and does not consume stored comparison/timeline APIs. | Send measurement confirmation; add stored comparison and timeline calls. | Backend API. | Medium. |
| `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx` | One large upload-only wizard with no measurement gate. | Orchestrate prerequisites, upload/camera choice, three views, consent, submission, and start. Move camera and measurement details into dedicated components. | Profile context, processor, camera. | High. |
| `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.tsx` | Finds previous analysis through N+1 calls and renders client comparison. | Branch legacy/v4 rendering, request stored comparison, and remove previous-analysis discovery. | API and result components. | High. |
| `frontend/src/features/bodyPhotos/BodyAnalysisResult.tsx` | Displays confidence percentages, raw LLM Persian, v3 goal reasoning, 39 checklist items, and empty groups. | Render deterministic v4 first impression, direction, four indicators, sparse insights, interactive map, disclaimer, and reviews. Keep a contained legacy renderer. | Experience contract. | High. |
| `frontend/src/features/bodyPhotos/BodyAreaMap.tsx` | Draws a generic line figure with coordinate dots and confidence percentages. | Replace with accessible semantic male/female/neutral front/back SVG map. | New SVG assets and mapping. | High: accessibility and asset alignment. |
| `frontend/src/features/bodyPhotos/ProgressComparison.tsx` | Recomputes transitions client-side. | Render backend comparison v1/v2 semantics and provenance. | Timeline/comparison API. | Medium. |
| `frontend/src/features/bodyPhotos/BodyProgressPage.tsx` | Shows session lists and misleading `Bod.png`. | Render scan timeline, latest summary, measurement changes, review state, and comparison entry points while preserving incomplete-session resume/delete. | History API. | High. |
| `frontend/src/features/bodyPhotos/SpecialistReviewStatus.tsx` | Shows existing state with minimal styling. | Preserve data contract; make pending/non-approved explicitly red and approved green, with label/icon so color is not the only cue. | Existing review API. | Low. |
| `frontend/src/features/bodyPhotos/bodyPhotos.css` | Styles old scanner image, dot map, checklist, and confidence UI. | Add camera, measurement step, v4 result, SVG map, timeline, slider, responsive and reduced-motion styles. Remove obsolete selectors after tests migrate. | All new UI. | Medium. |
| `frontend/src/i18n/fa.ts` | Contains old confidence/checklist/goal-copy strings. | Add curated natural Iranian Persian keys for v4. Preserve keys needed by legacy rendering. | Presentation keys. | Medium. |
| `frontend/src/i18n/en.ts` | Mirrors old product strings. | Add equivalent English fallback keys. | Presentation keys. | Low. |
| `frontend/src/features/profile/ProfileFormFields.tsx` | Embeds height, weight, and circumference controls inside `BodyGoalFields`. | Extract a reusable body-measurement field group used by both profile and Body Analysis prerequisites. Existing profile UI must remain behaviorally identical. | Wizard prerequisite step. | Medium. |
| `frontend/src/features/profile/profileValidation.ts` | Circumferences are optional in normal profile validation. | Add a separate Body Analysis prerequisite validator where all three circumferences are required. Do not make them globally required for profile completion. | Wizard only. | Medium. |

### Frontend: NEW FILES

| File | Responsibility |
|---|---|
| `frontend/src/features/bodyPhotos/BodyAnalysisRequirementsStep.tsx` | Display current profile/measurements, edit through existing profile update action, and require explicit confirmation. |
| `frontend/src/features/bodyPhotos/GhostCameraCapture.tsx` | Camera permission, stream lifecycle, timer, capture, retake, camera toggle, and upload fallback. |
| `frontend/src/features/bodyPhotos/GhostOverlayGuide.tsx` | View-specific privacy cut line and loose front/side/back silhouette. |
| `frontend/src/features/bodyPhotos/livePoseGuide.ts` | Separate MediaPipe VIDEO-mode detector and throttled advisory guidance. |
| `frontend/src/features/bodyPhotos/BodyAnalysisV4Result.tsx` | V4-only result composition, separate from contained legacy rendering. |
| `frontend/src/features/bodyPhotos/BodyTimeline.tsx` | Render scans and deterministic change summaries. |
| `frontend/src/features/bodyPhotos/BeforeAfterSlider.tsx` | Accessible protected-photo comparison. |
| `frontend/src/features/bodyPhotos/bodyMapRegions.ts` | Map body areas to stable SVG region IDs and view availability. |
| `frontend/src/assets/body-map/male-front.svg` | Semantic male front artwork. |
| `frontend/src/assets/body-map/male-back.svg` | Semantic male back artwork. |
| `frontend/src/assets/body-map/female-front.svg` | Semantic female front artwork. |
| `frontend/src/assets/body-map/female-back.svg` | Semantic female back artwork. |
| `frontend/src/assets/body-map/neutral-front.svg` | Semantic neutral front artwork. |
| `frontend/src/assets/body-map/neutral-back.svg` | Semantic neutral back artwork. |

### Frontend: SHOULD REMAIN UNCHANGED

| File | Reason |
|---|---|
| `frontend/src/features/bodyPhotos/processor.ts` | Camera output must reuse this exact post-capture pipeline. |
| `frontend/src/features/bodyPhotos/mediaPipePoseDetector.ts` | Existing IMAGE-mode captured-photo validation remains correct. Live guidance uses a separate adapter. |
| `frontend/src/features/bodyPhotos/mediaPipeBodySegmenter.ts` | Segmentation remains post-capture only. |
| `frontend/src/features/profile/api.ts` | Existing PATCH API is sufficient. |
| `frontend/src/features/profile/ProfileContext.tsx` | Already exposes profile and `updateProfile`. |
| `frontend/src/features/profile/types.ts` | Existing sex, goal, and measurement types are sufficient. |
| `frontend/src/App.tsx` | Existing Body Progress routes are sufficient unless the implementation deliberately adds a separate comparison route. |

### DELETE / DEPRECATE

| File | Action | Reason |
|---|---|---|
| `frontend/src/features/bodyPhotos/comparison.ts` | Delete after backend comparison UI is active. | Duplicate client authority. |
| `frontend/src/features/bodyPhotos/comparison.test.ts` | Delete with the obsolete module. Replace with backend-contract component tests. | Tests removed behavior. |
| `frontend/public/body-analysis/Bod.png` | Deprecate immediately; delete once no references remain. | Male-only, unrealistic, and includes unsupported fake metrics. |

## 13. Files That Must Not Be Touched

Luna Max must not modify:

- Any workout-engine file.
- Any exercise catalog or training-template file.
- Any nutrition file.
- Any authentication behavior.
- Any provider routing or credential behavior.
- Agent Service prompt ownership.
- Existing database migrations.
- Existing body-photo deletion, consent, private storage, or resumable-session semantics.
- Unrelated tracked or untracked user files.

The following regression boundary is mandatory:

```text
Body Analysis UI/provider changes
        ↓
v4 deterministic normalizer
        ↓
existing NormalizedBodyAnalysis
        ↓
existing body_analysis_resolver.py
        ↓
existing program_engine/body_analysis.py
        ↓
existing engine.py
```

Only the normalizer and response/read-model layers may adapt v4.

## 14. Test Changes

### Existing tests that must remain valid

Backend:

- Body-photo owner isolation.
- Private media access.
- Trusted-origin mutation checks.
- Consent recording.
- Three-view uniqueness.
- Session resume and delete.
- Image signature/dimension validation.
- Provider strict-schema conversion.
- Provider retry and safe errors.
- Result versioning.
- Coach and doctor independent approvals.
- One reviewer cannot approve both roles.
- Specialist corrections create a new result version.
- Comparison idempotency and owner isolation.
- Comparison failure does not fail analysis.
- Workout resolver provenance.
- Program-engine confidence, priority, safety, and trace tests.
- Workout-cycle body-progress tests.

Frontend:

- Upload processor format and quality validation.
- Front/back ambiguity behavior.
- Side-view validation.
- Segmentation and gray background.
- Resume all incomplete sessions.
- Accessible delete dialog.
- Existing API error behavior.

### Existing tests requiring updates

- `backend/tests/body_analysis/test_normalization.py`
  - Preserve v1/v2/v3 cases.
  - Add v4 projection and evidence downgrade cases.

- `backend/tests/body_analysis/test_execution_and_reviews.py`
  - Replace new-execution v3 fixtures with v4.
  - Add immutable snapshot and retry behavior.
  - Preserve legacy persistence fixtures.

- `backend/tests/body_analysis/test_runtime.py`
  - Expect prompt/schema v4.

- `backend/tests/body_analysis/test_analysis_api.py`
  - Add measurement-confirmation request.
  - Validate experience result and legacy unions.

- `backend/tests/body_analysis/test_progress_comparison.py`
  - Preserve v1.
  - Add measurement-backed v2 and provenance.

- `backend/tests/body_analysis/test_providers.py`
  - Add v4 strict-schema fixture without changing generic transport behavior.

- `agent-service/tests/test_task_prompt_ownership.py`
  - Add the v4 prompt marker to the assertion that Fitsho owns task prompts.
  - Do not add v4 logic to Agent Service.

- `frontend/src/features/bodyPhotos/BodyPhotoWizard.test.tsx`
  - Add prerequisite and camera tests.
  - Preserve upload/resume tests.

- `frontend/src/features/bodyPhotos/BodyAnalysisResultPage.test.tsx`
  - Replace confidence/checklist expectations with v4 experience.
  - Keep one v2/v3 legacy-rendering fixture.

- `frontend/src/features/bodyPhotos/BodyProgressPage.test.tsx`
  - Replace `Bod.png` expectations with timeline data.
  - Preserve incomplete-session and deletion expectations.

- `frontend/src/features/bodyPhotos/api.test.ts`
  - Add start payload, stored comparison, and timeline requests.

### New backend test cases

- Missing height blocks queue.
- Missing weight blocks queue.
- Each missing circumference blocks queue.
- Neutral sex values are accepted.
- Snapshot is captured before asynchronous execution.
- Profile updates after queue do not change provider input.
- Retry without photo changes reuses snapshot.
- Changed photos require fresh confirmation/snapshot.
- Snapshot is retained after provider failure.
- V4 rejects duplicate/missing anatomical areas.
- V4 rejects free-form extra fields.
- V4 rejects medical, genetic, body-fat, posture, pain, and diagnosis content structurally.
- V4 rejects training emphasis on stronger/balanced/not-assessable findings.
- V4 caps unsupported high evidence.
- Posture compatibility finding is always uncertain.
- Specialist correction changes the v4 body-map classification.
- Goal direction reuses current `FitnessGoal`.
- Legacy `improve_fitness` requests goal confirmation.
- Timeline is owner-only.
- First scan has no comparison.
- Exact snapshots produce exact deltas.
- Legacy scans do not receive guessed measurement values.
- Comparison visual statements are marked as visual observations.
- No Alembic migration is introduced.

### New frontend test cases

- Missing measurements block photo capture.
- Measurement update uses existing profile API.
- Explicit confirmation is required.
- Camera permission accepted.
- Permission denied falls back to upload.
- Insecure context falls back to upload.
- Stream tracks stop on close/unmount/navigation.
- Timer capture produces a `File`.
- Fixed privacy cut is applied.
- Mirrored preview does not accidentally flip stored output.
- Camera file calls the same processor used by upload.
- Live warnings do not hard-disable capture.
- Slow/failed live MediaPipe leaves the overlay usable.
- Male/female/neutral body-map selection.
- Front/back map switching.
- Keyboard and touch region selection.
- Color is not the only classification cue.
- No numeric confidence percentages in v4.
- Empty insight groups are not rendered.
- Review pending is red/labeled; approved is green/labeled.
- Timeline shows exact measurement provenance.
- Visual observations have a disclaimer.
- Before/after slider works for all views and keyboard input.

## 15. Main Risks

1. **Provider strict-schema rejection**
   - Keep v4 schema small.
   - Preserve recursive strict-schema normalization.
   - Test the exact outgoing schema.

2. **Incorrect workout influence**
   - Freeze resolver and engine files.
   - Test v4 projection separately.
   - Allow only high evidence to cross the existing `0.7` engine gate.

3. **Specialist correction/UI conflict**
   - Derive the v4 map from the current normalized result version.
   - Never render raw provider classifications directly.

4. **Measurement race**
   - Capture the snapshot synchronously during queue.
   - Never reread profile data inside AI execution.

5. **Camera frustration**
   - Keep alignment advisory.
   - Preserve upload fallback.
   - Run hard checks only after capture.

6. **Camera performance**
   - Throttle live inference.
   - Use low-resolution frames.
   - Disable live pose checks rather than blocking the UI on slow devices.

7. **Privacy regression**
   - No face model.
   - No video recording.
   - No raw live-frame upload.
   - Fixed visible privacy crop.
   - Existing private storage remains unchanged.

8. **Misleading product claims**
   - Remove potential, body-fat, genetic, diagnosis, posture, and physique-score claims.
   - Distinguish recorded measurements from visual observations.

9. **Legacy rendering**
   - Preserve explicit v1/v2/v3 fixtures.
   - Do not rewrite stored rows.

10. **Asset quality**
    - Do not ship the current `Bod.png`.
    - Body-map SVGs require original or licensed, reviewed artwork with stable region IDs.

## 16. Step-by-Step Implementation Order

Each phase is one logical step. Run focused checks, commit, and push before starting the next phase. Stage only explicit task files.

### Phase 0 — Baseline and protection

Files: none.

Actions:

1. Confirm branch and remote.
2. Record `git status`.
3. Do not remove or stage unrelated untracked files.
4. Run current focused Body Analysis, Body Photos, comparison, workout influence, and frontend body-photo tests.
5. Record failures before any change.

No commit.

### Phase 1 — Evidence-only v4 provider contract

Main files:

- `backend/app/body_analysis/schemas.py`
- `backend/app/body_analysis/normalization.py`
- `backend/tests/body_analysis/test_normalization.py`
- `backend/tests/body_analysis/test_providers.py`

Actions:

1. Write failing v4 schema and projection tests.
2. Add v4 evidence models.
3. Add strict structural validation.
4. Add deterministic 13-area projection.
5. Preserve v1/v2/v3 code paths.
6. Run focused tests, Ruff, and mypy.

Commit:

```text
feat(body-analysis): add evidence-only v4 contract
```

### Phase 2 — Immutable measurement snapshot

Main files:

- `backend/app/body_analysis/service.py`
- `backend/app/body_analysis/api_schemas.py`
- `backend/app/body_analysis/router.py`
- `backend/tests/body_analysis/test_execution_and_reviews.py`
- `backend/tests/body_analysis/test_analysis_api.py`

Actions:

1. Add start-request confirmation schema.
2. Add required-field validation.
3. Capture snapshot during queue.
4. Assign new raw-result dictionaries instead of mutating SQLAlchemy JSON in place.
5. Preserve snapshot when adding the provider result.
6. Implement retry snapshot rules.
7. Ensure provider execution reads only the captured snapshot.
8. Run focused tests, Ruff, and mypy.

Commit:

```text
feat(body-analysis): snapshot confirmed scan measurements
```

### Phase 3 — Deterministic experience read model

Main files:

- `backend/app/body_analysis/presentation.py`
- `backend/app/body_analysis/api_schemas.py`
- `backend/app/body_analysis/router.py`
- `backend/app/body_analysis/runtime.py`
- related backend tests
- `agent-service/tests/test_task_prompt_ownership.py`

Actions:

1. Switch new executions to v4.
2. Implement deterministic goal direction.
3. Implement four indicators.
4. Implement first-impression and insight keys.
5. Assemble `experience_result`.
6. Ensure current normalized result version overrides provider evidence.
7. Return legacy `visual_result` unchanged for v2/v3.
8. Verify Agent Service remains task-agnostic.

Commit:

```text
feat(body-analysis): expose deterministic v4 experience
```

### Phase 4 — Measurement-backed comparison and timeline API

Main files:

- `backend/app/body_analysis/comparison_schemas.py`
- `backend/app/body_analysis/comparison_service.py`
- `backend/app/body_analysis/history_schemas.py`
- `backend/app/body_analysis/history_service.py`
- `backend/app/body_analysis/history_router.py`
- `backend/app/main.py`
- comparison/history tests

Actions:

1. Add comparison v2.
2. Calculate snapshot measurement deltas.
3. Add visual observation transitions.
4. Add persistent priorities and provenance.
5. Add owner-scoped timeline query.
6. Preserve comparison v1 endpoint and data.
7. Verify comparison failures remain non-blocking.

Commit:

```text
feat(body-progress): add measurement-backed timeline
```

### Phase 5 — Frontend prerequisite gate

Main files:

- `frontend/src/features/profile/ProfileFormFields.tsx`
- `frontend/src/features/profile/profileValidation.ts`
- `frontend/src/features/bodyPhotos/BodyAnalysisRequirementsStep.tsx`
- `frontend/src/features/bodyPhotos/BodyPhotoWizard.tsx`
- `frontend/src/features/bodyPhotos/api.ts`
- `frontend/src/features/bodyPhotos/types.ts`
- tests and i18n

Actions:

1. Extract reusable measurement fields.
2. Add Body Analysis-specific required validation.
3. Add explicit current-measurement confirmation.
4. Pass confirmation to the start API.
5. Preserve normal profile optional-circumference behavior.
6. Preserve session resume and delete behavior.

Commit:

```text
feat(body-analysis): require confirmed scan measurements
```

### Phase 6 — Ghost Camera

Main files:

- `GhostCameraCapture.tsx`
- `GhostOverlayGuide.tsx`
- `livePoseGuide.ts`
- `BodyPhotoWizard.tsx`
- `bodyPhotos.css`
- tests and i18n

Actions:

1. Implement secure-context and capability detection.
2. Implement stream lifecycle.
3. Add front/environment camera toggle.
4. Add privacy cut and silhouettes.
5. Add throttled advisory pose checks.
6. Add timer, capture, retake, and confirm.
7. Convert capture to `File`.
8. Pass it through the existing processor.
9. Preserve upload fallback.
10. Test cleanup and privacy behavior.

Commit:

```text
feat(body-photos): add guided in-app camera capture
```

### Phase 7 — V4 result and interactive map

Main files:

- `BodyAnalysisV4Result.tsx`
- `BodyAnalysisResult.tsx`
- `BodyAnalysisResultPage.tsx`
- `BodyAreaMap.tsx`
- `bodyMapRegions.ts`
- six SVG assets
- `SpecialistReviewStatus.tsx`
- CSS, i18n, and tests

Actions:

1. Add explicit v4/legacy rendering branch.
2. Render deterministic first impression and direction.
3. Render four indicators.
4. Add SVG map interaction.
5. Render only meaningful insights.
6. Remove all v4 confidence percentages.
7. Keep review and disclaimer visible.
8. Stop referencing `Bod.png`.

Commit:

```text
feat(body-analysis): add interactive v4 physique result
```

### Phase 8 — My Body Over Time

Main files:

- `BodyProgressPage.tsx`
- `BodyTimeline.tsx`
- `ProgressComparison.tsx`
- `BeforeAfterSlider.tsx`
- `api.ts`
- `types.ts`
- CSS, i18n, and tests

Actions:

1. Consume timeline API.
2. Remove N+1 previous-analysis discovery.
3. Delete client comparison authority.
4. Show exact measurement changes and provenance.
5. Show visual transitions and limitations.
6. Add before/after slider.
7. Preserve incomplete-session resume/delete.
8. Delete obsolete `comparison.ts`, its test, and unused `Bod.png`.

Commit:

```text
feat(body-progress): add longitudinal body comparison
```

### Phase 9 — Full regression and runtime verification

Backend checks:

```bash
cd backend
ruff check
mypy
pytest tests/body_analysis tests/body_photos tests/profile tests/workout_cycles
pytest tests/workouts/test_body_analysis_resolver.py
pytest tests/workouts/program_engine/test_body_analysis_influence.py
pytest tests/workouts/program_engine/test_goal_priority_body_analysis.py
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run test
npm run build
```

Agent Service checks:

```bash
cd agent-service
pytest tests/test_task_prompt_ownership.py tests/test_generate_api.py tests/test_image_api.py
```

Runtime acceptance:

1. Upload flow: front/side/back.
2. Camera flow: front/side/back.
3. Permission denial fallback.
4. Missing measurement error.
5. Successful v4 Agent Service analysis.
6. Successful v4 direct-provider analysis if configured.
7. Pending coach/doctor red states.
8. Approved green states.
9. Specialist correction updates body map.
10. Second scan creates stored comparison.
11. Timeline shows exact measurement delta.
12. Before/after slider loads protected images.
13. Workout generation consumes only normalized v4 projection.
14. Existing v2/v3 stored result still renders.
15. No new migration exists.
16. Review `git diff --check` and staged allowlist.

Final commit only if verification fixes were required. Use a message describing the actual correction.

## 17. Features Not to Build Now

Do not build:

- Body-fat percentage estimation.
- Muscle-mass estimation.
- Medical diagnosis.
- Posture diagnosis.
- Pain or injury inference.
- Genetic potential.
- Bodybuilding potential.
- Competitive physique scoring.
- Beauty or attractiveness scoring.
- “Ideal” V-taper or waist-to-hip thresholds.
- Automatic goal replacement.
- Automatic profile-goal mutation.
- Automatic face detection.
- Automatic face tracking.
- Recorded camera video.
- Live segmentation.
- Real-time cloud upload.
- Raw pixel-to-pixel progress measurement.
- A second old-photo/new-photo LLM call.
- 3D body reconstruction.
- A new review system.
- A new measurement table.
- A camera-specific backend upload API.
- Any workout-engine redesign.

## 18. Final Decision

Do not approve the proposed document as an implementation specification in its current form.

Approve the product direction with the following replacement architecture:

- Evidence-only provider v4.
- Deterministic Fitsho presentation.
- Existing normalized 13-area workout adapter.
- Immutable analysis-time input snapshot in existing JSON.
- Advisory Ghost Camera with one shared post-capture pipeline.
- Semantic interactive SVG body map.
- Deterministic measurement-backed history.
- Existing coach/physician review system.
- No database migration.
- No workout-engine modification.
- No bodybuilding-potential metric.
- No user-facing confidence percentages.
- No extra historical AI call.

This is the recommended long-term architecture for Fitsho Body Analysis.
