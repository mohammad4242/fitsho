# Fitsho Nutrition implementation design

Status: Task 0 design with Task 1 and Task 2 implementation records. The Task 3
scientific policy was explicitly approved on 2026-08-05. Later-task tolerance,
price, photo, adherence, and operational policies still require their staged
approvals before the corresponding production work.

## Current repository audit

### Profile, onboarding, routing, and workouts

`UserProfile` is currently a training profile: it owns display name, birth date,
sex, height, goal, experience, weekly training, location, equipment, cautions,
duration, and physical limitations. `BodyMeasurement` is a separate append-only
weight/circumference history. `POST`, `PATCH`, and `GET /api/v1/profile` are
authenticated and ownership-scoped.

The React onboarding is a three-step training form. `ProfileProvider` resolves
the profile to `missing`, `ready`, or an error state. `OnboardingRoute` only
allows `missing`, while `CompletedProfileRoute` only allows `ready`; all member
routes (dashboard, workouts, body photos, and exercises) currently sit behind
the latter. Existing profile validators reject ages outside 18--100.

Workout generation reads the existing profile and its body-measurement history.
It must retain this contract throughout nutrition work. In particular, neither
nutrition mode nor an incomplete nutrition profile may make an established
training user lose access to workout, history, body-analysis, or exercise routes.

### Reviews, AI, uploads, jobs, and administration

The body-analysis module already provides the closest review precedent:
append-only result versions and reviews reference an exact version, reviewer,
role, decision, notes, and timestamp. `UserSpecialistRole` distinguishes
specialist authorization from `User.is_admin`; current review endpoints require
both admin access and an assigned specialist role.

AI administration has encrypted provider credentials in
`ai_provider_credentials`; only a masked suffix is returned. Encryption uses
`AI_CREDENTIAL_ENCRYPTION_KEY`. `ai_task_configs` stores enablement, models,
fallbacks, request limits, routing restrictions, health/test state, and audit
events. The model catalogue persists image-input and structured-output support.
The existing OpenRouter client uses `/api/v1/chat/completions`, validates
structured responses, and captures usage/cost. Food estimation should extend
these patterns with a new task type, not bypass them or use an environment key.

Body photos establish a private-upload pattern: validated and normalized image
files are atomically placed under `var/private`, are ownership-scoped, and have
queued cleanup records. Body analysis uses FastAPI `BackgroundTasks`; there is no
durable queue, scheduler, dead-letter store, or cross-process job runner today.
Public exercise media is separate under `/media`. Admin access is currently the
single `is_admin` flag, augmented by specialist-role rows for reviews.

Alembic migrations and SQLAlchemy declarative models are the database pattern;
FastAPI routers, Pydantic schemas, services, and focused backend/frontend tests
are the application pattern. Persian is the primary i18n language and the UI is
already RTL-aware. There is no food catalogue, nutrition plan, nutrition tracking,
price adapter, nutrition-specific review, or supplement model.

## Proposed domain boundaries

Create an `nutrition` package with submodules only when their task is reached:

| Boundary | Responsibility | Must not own |
| --- | --- | --- |
| `nutrition.profile` | Product mode, nutrition-specific settings, shared-profile completion | duplicate body fields |
| `nutrition.safety` | Declarations, policy versions, deterministic safety decision | diagnosis or prescription |
| `nutrition.targets` | Versioned deterministic estimates and nutrient targets | AI calls or food selection |
| `nutrition.catalogue` | Verified foods, nutrients, units, recipes/templates | mutable plan snapshots |
| `nutrition.pricing` | Quotes, mappings, freshness, provider selection | planner rules |
| `nutrition.planning` | Revisioned weekly plans, validation, costed quantities | current mutable catalogue data |
| `nutrition.tracking` | Confirmed consumption, check-ins, adherence aggregates | unconfirmed AI output |
| `nutrition.photo_estimation` | Temporary images, structured candidate detection, confirmation | authoritative nutrition facts |
| `nutrition.reviews` | Physician/coach review of exact revisions | admin authorization policy |
| `nutrition.supplements` | Catalogue and dual approval of an exact recommendation | automatic activation |

### Unified profile and compatible migration

Keep `user_profiles` as the source of truth for existing shared fields and
`body_measurements` as the source of truth for current/historical weight. Do not
add nullable nutrition fields to `user_profiles` and do not create another body
profile. Task 1 adds `product_mode` with no permanent database default for new
rows. Its migration backfills every existing profile to `TRAINING`, then makes
the API require a mode for newly created accounts. A temporary migration-only
default/check sequence may be used solely to backfill safely, then removed.

Proposed components are one-to-one `nutrition_profiles`, `medical_profiles`, and
`structured_exercise_profiles`, plus normalized child tables for conditions,
medications, allergies/intolerances, exclusions, preferences, pantry foods, and
cooking capabilities. A derived completion service returns the specified
capability state; it is not a fragile persisted boolean. New route guards use
that state: training-ready routes remain available to `TRAINING` users while
nutrition routes require nutrition completion and the relevant review state.

### Proposed persistent models and snapshots

All money is integer IRR, quantities are Decimal plus a normalized unit, and
all timestamps are UTC. IDs are UUIDs. Mutable master data is never used to
reinterpret historical plans or logs.

| Area | Proposed models |
| --- | --- |
| Policy | `nutrition_policies`, immutable `nutrition_policy_versions`, `medical_condition_policies`, `planner_versions`, and versioned formula/price/adherence/photo/supplement policy references |
| Food | `foods`, `food_data_versions`, `food_units`, `meal_templates`, `meal_template_items`, and source/provenance records |
| Price | `price_providers`, `price_provider_food_mappings`, immutable `food_price_quotes`, provider-health events, and admin-verification records |
| Plans | `weekly_meal_plans`, immutable `meal_plan_revisions`, day/meal/item snapshots, validation results, selected quote snapshots, exact shopping-list item snapshots, and change/lock records |
| Tracking | `consumption_entries`, immutable nutrient snapshots, quick check-ins, daily/weekly adherence aggregates, and user meal feedback |
| Photos | `food_photo_requests`, private file/cleanup rows, candidate-item rows, and confirmation/edit audit rows |
| Reviews | `nutrition_reviews`, structured physician edits, reviewer-role assignments, and activation decisions linked to a plan revision |
| Supplements | `supplement_catalogue`, versioned supplement facts, recommendations, and separate physician/coach approval rows tied to recommendation revision |

Plan, price, food-data, policy, formula, planner, and adherence versions are
stored on every revision. Editing a plan creates a revision; reviews and dual
approvals apply to that exact revision and are invalidated by a replacement.

### API, roles, and operational design

Add versioned `/api/v1/nutrition/*` routes; leave current profile and workout
responses unchanged. Task 1 may add additive fields/endpoints only. All user
resources are owner-filtered. Add explicit `PHYSICIAN` and `COACH` specialist
roles (the existing `UserSpecialistRole` pattern), and require authorization in
addition to a role; an administrator is not implicitly a clinician. Admins manage
catalogue, providers, policies, and AI task configuration. Physician actions can
review/edit plan revisions; coach actions can review coaching concerns and approve
supplements. Every supplement recommendation needs different role approvals from
the approved physician and coach policy; no automatic activation exists.

Until durable jobs exist, a task that needs retry, scheduling, or reliable
notification must either remain synchronous with clear bounded failure behavior
or wait for an approved durable-job foundation. FastAPI `BackgroundTasks` is
acceptable only for best-effort cleanup/execution that is safely retryable by a
user/admin. No medical data or image bytes go into normal logs; retain a
correlation ID and safe error code only.

## Proposed delivery map

1. Task 1: product mode, shared profile aggregate, compatible route guards.
2. Task 2: age/safety screen, nutrition profile, declarations, review foundation.
3. Task 3: approved deterministic energy/nutrient target engine.
4. Task 4: verified food catalogue and structured meals.
5. Task 5: price-provider framework and approved data ingestion.
6. Task 6: revisioned budget-aware planner and exact shopping list.
7. Task 7: replacements, locks, partial regeneration, and validation.
8. Task 8: confirmed consumption tracking and adherence views.
9. Task 9: OpenRouter food-photo estimation and confirmation flow.
10. Task 10: physician/coach panels, plan review, supplements, administration,
    documentation, and end-to-end hardening.

The exact later-task names/order must be reconciled with Section 48 before each
task; this map is architectural grouping, not authorization to combine tasks.

## Scientific-policy approval table

The following adult-MVP policy was explicitly approved on 2026-08-05 for Task 3.
A personal clinical restriction always overrides it. The engine must require
review or report insufficient data rather than infer a missing clinical rule.

| Metric or rule | Formula / threshold | Population | Source | Hard floor / maximum | Preferred target / range | Planner tolerance | Confidence / fallback | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BMR | Mifflin--St Jeor using age, height, weight, and an optional metabolic equation basis | 18--100, non-pregnant adults without manual-only status | Mifflin 1990, PubMed PMID 2305711 | none | report estimate, not measurement | n/a | return the female/male coefficient range when basis is skipped; lower confidence outside ages 19--78 | equation error and body-composition variation |
| TDEE | BMR x approved non-exercise multiplier (1.20/1.30/1.40/1.50) + weekly net structured-exercise kcal / 7 | same | NASEM 2023 energy context; 2024 Adult and Older Adult Compendia | never full activity factor plus exercise | report estimate and uncertainty | daily target +/-10% | explicit no-exercise is zero; missing required exercise input blocks an estimate | self-reported movement and intensity |
| Goal energy change | loss/fat loss preferred -15% (allowed -10% to -20%); gain without exercise +5%; gain with exercise preferred +10% (allowed +5% to +15%); muscle gain +5% to +10%; recomp 0% to -5%; maintenance 0% | automatic adults with compatible goal/exercise state | approved Fitsho policy; individualized monitoring | automatic calorie target not below estimated BMR | conservative end of each range | see tolerance table | low confidence narrows change; incompatible no-training muscle goals require reselection | estimate requires outcome monitoring |
| Protein | 0.8 g/kg calculation-weight minimum; preferred 1.0 no-training, 1.2 deficit/no-training, 1.4 endurance, 1.6 resistance/mixed, and 1.8 resistance/deficit; automatic ceiling 2.2 | adults without renal/manual policy | National Academies DRI; Morton 2018; Tagawa 2020; ESPEN adjusted-weight method | 0.8 g/kg; <=2.2 g/kg | goal- and training-specific value | min 0%; preferred -10% | BMI >25 uses reference weight at BMI 25 + 0.33 of excess; kidney/manual states block ordinary policy | predictive target, not measured need |
| Fat | 15% energy minimum and 30% maximum | automatic adults | WHO Healthy diet, 2026 | >=15%; <=30% | 20--30% | min 0%; preferred +/-10% | missing fatty-acid data prevents a compliant food-plan claim | not a treatment diet |
| Carbohydrate | 45--75% energy with 130 g/day floor | automatic adults | WHO Healthy diet, 2026; National Academies DRI | >=130 g/day and normally >=45% energy | individualized within range after protein and fat | +/-10% target only within hard limits | conflicting macro constraints return a structured conflict | clinical low-carb diets excluded |
| Fibre | at least 25 g/day; preferred 14 g/1000 kcal | automatic adults | WHO Healthy diet, 2026; National Academies DRI | >=25 g/day | max(25 g, 14 g/1000 kcal) | 0% daily deficit; weekly only for warning | missing fibre prevents a compliant food-plan claim | GI conditions may require review |
| Free sugar | <10% energy | automatic adults | WHO Healthy diet, 2026 | <10% | <=5% | 0% excess strict; no flexible excess | missing free-sugar data prevents a compliant claim | free and added sugar must not be added together |
| Saturated fat | <10% energy | automatic adults | WHO Healthy diet | <10% | as low as practical with adequacy | 0% strict excess | unavailable data -> warning/exclusion from compliant plan | not disease-specific lipid treatment |
| Trans fat | <1% energy and no industrial trans-fat claim | automatic adults | WHO Healthy diet | <1% | as close to zero as data permits | 0% strict excess | unavailable data -> no compliant claim | incomplete labels |
| Sodium | <2,000 mg/day | automatic adults | WHO sodium guidance | <2,000 mg | lower only by clinician policy | 0% strict excess | missing sodium -> no strict plan | cooking salt/restaurant food uncertainty |
| Budget | monthly IRR / 4.345, summed from exact normalized quantities | all plans | task specification | strict budget: 0% excess | flexible: user-approved <=5% warning | strict 0%; flexible <=5% | missing verified quote -> no strict-live plan | prices vary by region/package |

Sources: [Mifflin--St Jeor original record](https://pubmed.ncbi.nlm.nih.gov/2305711/),
[WHO Healthy diet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet),
[National Academies DRI collection](https://nap.nationalacademies.org/collection/57/dietary-reference-intakes),
[2024 Adult Compendium](https://pmc.ncbi.nlm.nih.gov/articles/PMC10818145/),
[Older Adult Compendium](https://pmc.ncbi.nlm.nih.gov/articles/PMC10818108/),
[Morton protein meta-analysis](https://pubmed.ncbi.nlm.nih.gov/28698222/), and
[ESPEN adjusted-weight guidance](https://www.espen.org/files/ESPEN-Guidelines/European_guideline_on_obesity_care_in_patients_with_gastrointestinal_and_liver_diseases_Joint_ESPEN_UEG%20guideline.pdf).
The approved formulas, exact data flow, confidence rules, API, and persistence
design are recorded in the dedicated Task 3 design document.

## Planner-tolerance proposal

| Rule | Strict result | Flexible result | Warning | `INFEASIBLE` |
| --- | --- | --- | --- | --- |
| Daily calories | within +/-10% | within +/-15% if user explicitly accepts | >10% to 15% | >15% or a hard floor conflicts |
| Weekly calories | within +/-5% of target | within +/-7.5% with acceptance | >5% to 7.5% | >7.5% |
| Protein | never below hard minimum; preferred within -10%/+15% | preferred within -15%/+20% | preferred miss inside flexible band | hard minimum miss |
| Fat | no minimum miss; upper target +10% | upper target +15% | only within flexible band | minimum or hard maximum miss |
| Fibre | meet daily hard floor | weekly average only is not allowed | none for hard-floor miss | any daily miss |
| Sugar, saturated fat, trans fat, sodium | no hard maximum excess | none | no warning-only excess | any excess when data is available |
| Budget | 0% excess | <=5% with explicit acceptance | >0% to 5% | >5%, or strict price requirement unavailable |
| Repetition | max 2 identical main meals/week; max 3 if explicitly locked | locked meals exempt | exceeds variety goal only | never by itself |

All percentages are proposed policy constants to be versioned, not literals in
planner code. The planner must return a structured explanation for every warning
and unsatisfied constraint.

## Medical classification proposal

| Outcome | Proposed conditions / signals | Action |
| --- | --- | --- |
| `STANDARD_AUTOMATIC` | no declared condition requiring another outcome | normal deterministic draft/activation checks |
| `AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW` | controlled hypertension, lipid disorder, non-insulin-treated type 2 diabetes, stable GI condition, or prescribed restriction with sufficient structured details | generate a draft but block activation pending physician decision on its exact revision |
| `PHYSICIAN_MANUAL_PLAN_REQUIRED` | kidney disease/dialysis, liver disease, insulin-treated diabetes, pregnancy/breastfeeding, active eating-disorder diagnosis/symptoms, complex medication-food interaction, or clinician-required diet | no ordinary automatic plan; physician creates/substantially edits revision |
| `UNSUPPORTED_OR_HARD_BLOCKED` | under 18; emergency/danger symptoms; condition not covered by approved policy; missing essential safety data after declared high-risk condition | stable error/unsupported state; no plan, photo request, or supplement recommendation |

This is a configuration proposal, not medical advice. A physician must approve
the condition list and mappings before Task 2. The existing upper-age boundary
(100) remains unchanged unless a separate approved policy changes it.

## Price-provider feasibility and policy proposal

No permitted, documented, stable Iranian retailer API has been approved by this
Task 0 audit. The Ministry-linked historical food-price publication is useful as
evidence that official lists can exist, but it is from 1400/2021 and is neither
a current retail feed nor an API. The discovered commercial food-market API page
does not provide enough public evidence of terms, coverage, mapping, timestamps,
rate limits, and retailer provenance to approve it. Digikala and Torob internal
or undocumented APIs are explicitly excluded.

Therefore Task 5 must first implement only the specified provider abstraction:
`DatabaseManagedPriceProvider`, `ValidatedImportPriceProvider`, and a
development-only `SeedPriceProvider`. An external adapter needs written approval
and a recorded provider assessment covering authorization/terms, authentication,
rate limits, province/retailer coverage, package and unit semantics, IRR/IRT
normalization, effective timestamp, source payload retention, mapping success,
health checks, and exit/rollback plan. No scraping is approved.

Proposed price policy:

- Freshness: 24 hours for `LIVE_*`; 48 hours is `STALE`, never live.
- `LIVE_VERIFIED`: two independent fresh quotes for a common cost-significant
  food, normalized to IRR per base unit, with provider health and confidence.
- `LIVE_SINGLE_SOURCE`: one fresh approved source; display it, but strict live
  planning cannot use it for a cost-significant ingredient.
- `ADMIN_VERIFIED`: signed/admin-reviewed import with effective date; usable for
  non-strict planning only and never labelled live.
- `ESTIMATED` and `UNAVAILABLE`: visible states only; no fabricated current
  price. A strict-live plan is blocked when a cost-significant ingredient is not
  `LIVE_VERIFIED`.

Price source: [Ministry-linked official historical list](https://www.iana.ir/%D8%A8%D8%AE%D8%B4-%D8%A7%D9%82%D8%AA%D8%B5%D8%A7%D8%AF-%DA%A9%D8%B4%D8%A7%D9%88%D8%B1%D8%B2%DB%8C-5/98879-%D9%81%D9%87%D8%B1%D8%B3%D8%AA-%D9%82%DB%8C%D9%85%D8%AA-%D8%B1%D8%B3%D9%85%DB%8C-%D8%A7%D9%82%D9%84%D8%A7%D9%85-%D8%AE%D9%88%D8%B1%D8%A7%DA%A9%DB%8C-%D8%A7%D8%B9%D9%84%D8%A7%D9%85-%D8%B4%D8%AF).

## Food-photo policy and OpenRouter approach

Create a separate `FOOD_PHOTO_ESTIMATION` AI task configuration. Reuse encrypted
credentials, masked status, model catalogue, connection testing, routing
restrictions, timeout, fallback, model capability checks, structured validation,
usage/cost records, and audit logs. Before a request, the server validates
ownership/type/size, strips metadata where practical, records explicit
third-party-processing consent, stores a temporary private image, and sends only
the image plus minimum food-identification context. The OpenRouter image-input
guide supports multipart chat-completions content with an image URL or base64
image; this project should use base64 from private storage rather than expose a
public URL. Select only catalogue models marked image-capable and validate the
strict candidate schema before persistence.

The model provides guesses, portions, evidence, uncertainties, and confidence;
the verified food catalogue calculates nutrients. An unresolved item remains
unresolved. No photo result is a consumption entry until the user confirms or
edits it. Proposed confidence bands: `HIGH >=0.80`, `MEDIUM 0.50--0.79`, and
`LOW <0.50`; all require confirmation, while low confidence requires a manual
catalogue choice or approximate structured entry before logging. Default photo
retention is 30 days after request completion and 7 days after explicit deletion
request processing; derived confirmed nutrition snapshots are retained with the
user's consumption record, while raw model payload is minimized and expires with
the request unless needed for an active dispute/review. These periods need user
and privacy/legal approval.

Source: [OpenRouter image inputs documentation](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding).

## Adherence proposal, risks, and approval gates

For a day with sufficient confirmed data, compute weighted adherence as:

`0.35 * calorie_score + 0.25 * protein_score + 0.15 * diet_quality_score + 0.15 * meal_confirmation_score + 0.10 * budget_score`.

Each component is clamped to 0--1, deviations use the approved tolerance bands,
and a day is `INSUFFICIENT_DATA` rather than scored if less than 50% of planned
energy has confirmed/edited/captured evidence and no complete quick check-in is
provided. Weekly adherence is the mean of sufficient days only, with the count
shown. It must adjust future plans cautiously: never alter medical constraints,
hard exclusions, or approved targets without the relevant review. Formula
weights, the 50% threshold, and adaptation bounds require approval before Task 8.

Key risks: clinical classification is not a diagnosis; food composition and
Iranian retail price coverage may be incomplete; self-report/photo portions are
uncertain; body/medical/photos are sensitive; current background execution is
not durable; and role credentials/identity verification need a product/legal
operating policy. Mitigations are versioned snapshots, visible confidence and
freshness, conservative blocking, explicit consent, private storage/cleanup,
least-privilege roles, audit records, and no unsupported "live" or medical claim.

## Approval checklist and later-task gates

1. Unified-profile migration and additive API/route-guard direction.
2. The scientific-policy table and cited/source-audit gap for DRI values.
3. Planner tolerances and strict/flexible budget behavior.
4. The 24-hour freshness window, two-source strict-live rule, and no-external-
   adapter conclusion pending written provider authorization.
5. Medical classification mappings and specialist operating model.
6. Photo confidence/confirmation, retention periods, and consent wording.
7. Adherence formula, sufficiency threshold, and later adaptation limits.

Task 3 approval record: on 2026-08-05 the user selected the current mixed-source
policy (WHO, National Academies, Mifflin--St Jeor, and the 2024 activity
Compendia), approved an optional metabolic-basis question with a coefficient
range fallback, approved adjusted weight for high-BMI protein calculations, and
approved a required usual-intensity question wherever structured training is
part of the nutrition estimate.

Items 1, 2, and 5 have been exercised by the approved Task 1--3 designs. The
remaining entries continue to gate only the later tasks that consume them; the
Task 3 approval does not authorize later planner, pricing, photo, or adherence
work.

## Task 1 implementation record

Task 1 stores `product_mode` on the single `user_profiles` row. Selecting a mode
creates that row as an incomplete draft; it does not create a second profile.
Existing profiles are backfilled to `training`, while the database has no
permanent mode default. Legacy full-profile creation remains compatible and is
treated as training onboarding.

The additive endpoints are:

- `GET /api/v1/profile/status` for product mode and capability completion state.
- `POST /api/v1/profile/mode` for explicit mode selection or later mode changes.

The frontend loads status before the full training profile. Users without a
mode see the three unselected cards; `both` is visually recommended but not
preselected. Training users continue through the existing training form.
Nutrition and both-mode users remain behind onboarding guards until their
nutrition requirements are implemented in Task 2. Existing training-ready users
continue to reach workouts, body analysis, exercises, and dashboard routes.

## Task 2 implementation record

Task 2 keeps shared identity, birth date, sex, height, current weight, and goal
on the single `user_profiles` aggregate. Medical answers, medications, safety
decisions, nutrition preferences, cooking equipment, and food constraints are
stored in normalized nutrition tables. No duplicate training or nutrition user
profile was introduced.

The deterministic medical policy is seeded as immutable version
`medical-condition-v1`. Every safety submission creates a new append-only
decision with normalized reason codes. The four approved outcomes are returned
as structured API data; manual-only and unsupported outcomes stop guided
onboarding before budget and preference questions. These rules classify a
workflow and do not diagnose a condition.

The additive endpoints are:

- `GET` and `PUT /api/v1/profile/shared`
- `GET` and `PUT /api/v1/nutrition/safety`
- `GET` and `PUT /api/v1/nutrition/profile`
- `GET /api/v1/nutrition/review-requirement`

The individual monthly budget is an integer number of IRR. The derived weekly
allowance uses integer arithmetic exactly as
`floor(monthly_budget_irr * 12 / 52)`. Allergies, intolerances, refusals, and
other exclusions are typed relational rows so later planning stages can apply
them as hard constraints.

Nutrition and combined onboarding now follow a page-by-page coach flow: shared
information, early safety screening, the training branch for combined mode,
meal structure, budget, food preferences and exclusions, and confirmation.
Optional free-text and preference questions provide explicit skip controls.
Under-18 submissions return `AGE_NOT_SUPPORTED`; the established maximum age
of 100 remains unchanged. Training APIs reject incomplete or nutrition-only
profiles.

The physician-review table and review-requirement API are foundations only.
Task 2 does not create review assignments, professional decisions, meal plans,
energy targets, or food recommendations; those remain in their later staged
tasks.

## Task 2A implementation record

Nutrition onboarding no longer asks Cooking-domain questions. The existing
non-null Cooking columns and equipment rows remain in the database as legacy
data for backward compatibility, but new Nutrition writes do not require or
rewrite them. Ordinary preference capture is limited to liked and disliked
foods; allergies, intolerances, medical restrictions, and cultural exclusions
remain safety/nutrition context.

Meal structure now uses typed buckets for two, three, or four-plus main meals
and zero, one, two, or three-plus snacks. The migration backfills those buckets
and their effective planner slot counts from existing numeric values. Numeric
fields remain accepted as deprecated compatibility inputs and are normalized to
the typed buckets.

## Task 2B implementation record

Task 2B adds the immutable `micronutrient-dri-v1` policy foundation without
activating micronutrient-aware meal planning. It includes normalized policy
versions, source registry rows, and reference rows for the core adult MVP
nutrients: calcium, potassium, magnesium, iron, zinc, sodium, vitamin C,
vitamin D, vitamin B12, and folate/DFE.

Reference kinds remain distinct: `RDA`, `AI`, `EAR`, `UL`, and `CDRR` are
stored as typed values, and the schema also supports `MEDICAL_OVERRIDE`.
Potassium is represented with AI and no fabricated healthy-population UL.
Sodium stores AI and CDRR separately and has no sodium UL row. Magnesium's
seeded UL is marked supplemental-only. Most adequacy rows use a weekly-average
aggregation window; safety limits use a daily window. A dietary-reference gap
is explicitly non-diagnostic in the policy manifest.

The source registry records NASEM as the primary DRI authority and NIH ODS as
the cross-check source. Research/access date is 2026-08-08. Primary sources:

- https://nap.nationalacademies.org/collection/57/dietary-reference-intakes
- https://nap.nationalacademies.org/catalog/25353/dietary-reference-intakes-for-sodium-and-potassium
- https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/
- https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/
- https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/
- https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/
- https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
- https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
- https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/
- https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/

The policy is a source and reference foundation only. Task 2B does not yet
select user-specific rows in the estimate engine, score food candidates, or
perform micronutrient repair.

The policy manifest also records the deterministic interpretation boundary:
RDA is preferred over AI, EAR is never an individual hard minimum, and an UL
is only a safety ceiling within its stored scope. Medical overrides take
precedence over nutrient-specific safety limits, which take precedence over
healthy-population DRI rows. Adequacy is represented on a 0–100 scale with
weekly-average defaults; a weekly result requires four measured days and at
least 80% supported-nutrient coverage. Missing data is not treated as zero.
Repair remains bounded to three iterations, with five-percent calorie/macro
tolerances and rejection of any new hard safety violation.

Food composition mapping is reserved for USDA FoodData Central (or a verified
regional source with equivalent provenance). Requirement targets never come
from food-composition records; every future mapping must preserve source,
serving unit, nutrient form, confidence, and unit-conversion metadata.

## Task 3 implementation record

The deterministic estimate engine now resolves the selected adult
micronutrient RDA/AI rows from `micronutrient-dri-v1` by age, sex, and explicit
dietary pattern, then persists the selected reference, unit/form, aggregation
window, UL/CDRR metadata, source, policy version, and non-diagnostic
explanation with the estimate. `BOTH` mode uses an active Fitsho training plan
first and the training profile as an explicit fallback; nutrition-only mode
requires an explicit structured-exercise answer and supports no-training.

Macro minima are checked jointly against the calorie target before returning a
result. Preferred values are never allowed to hide a hard-minimum conflict;
the API returns `TARGET_INFEASIBLE` with reason codes when the configured
minimums cannot fit. Sodium exposes the 1,500 mg AI and 2,300 mg CDRR rather
than treating CDRR as a toxicity UL. All estimates retain formula/policy
versions, input snapshots, confidence, and explanation metadata.

## Task 4 implementation record

The verified food catalogue uses canonical gram quantities and per-100g
composition rows. Each composition row retains nutrient code, unit/form,
source, and confidence; a missing composition row remains unavailable rather
than becoming zero. Foods carry verified/draft/retired state and deterministic
roles for substantial main proteins, main staples, snacks, and flexible foods.

Structured catalogue meals store exact food grams and validate `MAIN_MEAL` or
`SNACK` role eligibility before calculating deterministic nutrient totals. The
current Iranian ingredient catalogue stores canonical unprepared food identities;
prepared dishes remain in a separate table and retired legacy cooked/grilled
identities stay readable only for history. Each composition row retains its
documented mapping provenance. The import normalizer accepts only verified
gram/kilogram quantity conversion and rejects duplicate nutrients or unsupported
units. Composition and pricing remain separate domains.

## Final conformance record

The completed Nutrition flow uses deterministic estimate, safety, catalogue,
price, planner, tracking, review, laboratory, and supplement services. A generated
safe plan is immediately visible but cannot become the adherence baseline before
exact-revision physician approval. Physician edits create immutable revisions and
rerun deterministic validation. Review assignment, effective-date activation,
one-active-plan enforcement, private/user-visible notes, and supplement changes
are authorization checked and audit preserving.

All member Nutrition routes are product-capability guarded. The physician UI is
server-role guarded and exposes exact plan data, input/safety snapshot, nutrient
validation, price/food provenance, structured food edits, laboratory review, and
structured supplement create/edit/status workflows. Tracking supports recent
foods, exact edits, planned-meal adjustments, date-range history, and user-confirmed
photo corrections. Member catalogue money is displayed in IRR; deprecated Toman
fields remain storage/API compatibility only.

## Task 14 security boundary

Nutrition private-file access is session-authenticated and additionally protected by short-lived,
actor-bound signed grants. Upload abuse limits and idempotency are persisted in PostgreSQL so they
work across workers and restarts. Food photos and lab binaries are stored outside public media and
removed by the retention scheduler while minimal audit history is retained. AI usage and price
provider health are persisted as content-free operational counters. See
`docs/nutrition-security-privacy.md` for the operational contract.
