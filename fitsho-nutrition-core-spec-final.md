# Fitsho Scientific, Budget-Aware, Micronutrient-Aware, Physician-Reviewed Nutrition Core Specification

> **Final implementation-ready revision:** this version incorporates the approved lifecycle, concurrency, target-feasibility, price-coverage, onboarding-safety, physician-review, and micronutrient rules. Codex must implement the staged tasks in Section 48 in order and must not invent alternate behavior where this specification is explicit.

**Revision focus:** user-selected main-meal/snack structure, authoritative micronutrient-aware planning, clear strict/flexible budget semantics, safe separation of plan visibility from tracking/activation, secure laboratory uploads, mandatory physician review of every Nutrition plan, physician-visible approval/version changes, and physician-managed supplement orders are first-class system requirements. Cooking and food-preparation logic remain outside this specification.

## 1. Purpose

You are working directly in the GitHub repository:

`mohammad4242/fitsho`

Extend Fitsho into one unified personal coaching application supporting:

- Personalized training
- Scientific personalized nutrition
- Body-development analysis
- Progress tracking
- Budget-aware weekly nutrition planning
- Low-friction calorie and food-consumption tracking
- Photo-assisted food and calorie estimation
- Mandatory physician review and approval for every generated Nutrition plan
- Secure laboratory-record review and physician-managed supplement ordering
- Live, traceable food-price data

Do not rename Fitsho.

Fitsho Nutrition is a scientific nutrition-planning system. Its primary responsibility is to determine what the user's body requires, compare that requirement with what is realistically achievable, and produce exact food quantities that satisfy the user's safety constraints, preferences, and budget as closely as possible.

The system must answer questions such as:

- How many calories does this user approximately require?
- What calorie target is appropriate for the selected goal?
- What are the user's protein minimum, preferred protein target, carbohydrate range, fat range, fibre target, and configured diet-quality limits?
- What is the ideal nutritional target?
- What is the minimum acceptable target under approved policy?
- What can actually be achieved with the user's budget and available verified foods?
- How large is the gap between the preferred target and the planned intake?
- Which foods and exact quantities should the user eat each day?
- How many calories, protein, carbohydrates, fat, fibre, sugars, saturated fat, trans fat, sodium, and supported micronutrients does each planned food or meal provide?
- Which core micronutrients are below, within, or above their applicable reference targets?
- Can a micronutrient gap be improved by a small food substitution or portion change without breaking calorie, macronutrient, safety, meal-role, or budget constraints?
- What does each ingredient cost, and what is the total daily and weekly cost?
- How many main meals and snacks does the user normally eat?
- How should the calculated daily calorie, protein, carbohydrate, fat, fibre, and diet-quality targets be distributed across that selected meal structure?

Example output concept:

```text
Breakfast
- Eggs: 3 items
- Whole-grain bread: 80 g

Meal totals:
- Calories: ... kcal
- Protein: ... g
- Carbohydrates: ... g
- Fat: ... g
- Fibre: ... g
- Sodium: ... mg
- Estimated cost: ... IRR

Lunch
- Chicken breast: 200 g
- Rice: 8 tablespoons or an exact gram equivalent defined by the verified serving conversion
- Salad or another verified compatible food: ... g

Meal totals:
- Calories: ... kcal
- Protein: ... g
- Carbohydrates: ... g
- Fat: ... g
- Fibre: ... g
- Sodium: ... mg
- Estimated cost: ... IRR
```

The exact values must always come from verified food-composition data and approved deterministic formulas. Never fabricate numeric nutrition values or prices.

Micronutrient reference targets must come from versioned authoritative dietary-reference policies, not from an LLM, not from arbitrary percentages, and not from unexplained hardcoded constants scattered through planner code. Most micronutrient reference values are selected primarily by age, sex, and supported life-stage or dietary modifiers rather than body weight.

A low planned dietary intake is not a diagnosis of a biological deficiency. Fitsho may report that a plan is below a dietary reference target; it must not claim that the user is clinically deficient without appropriate professional assessment and, where relevant, laboratory evidence.

Cooking is explicitly outside this Nutrition Core specification. Nutrition decides what foods and exact quantities belong in the plan; a separate future Cooking specification may decide how those foods are prepared.

OpenRouter is allowed only for photo-based food estimation inside the calorie counter. It must not be used for scientific calculations, nutrient targets, food selection, ingredient quantities, price selection, safety decisions, physician-review decisions, ordinary onboarding feedback, or normal plan explanations.


---

## 2. Current implementation status and next step

The following stages were completed before this specification was rewritten:

- Task 0 - Repository audit, provider research, and approved implementation design
- Task 1 - Product mode and unified profile foundation
- Task 2 - Early age, safety, medical-condition, and nutrition-profile foundation

Do not rerun Tasks 0, 1, or 2 from scratch.

Because the earlier Task 2 included fields that no longer belong to the Nutrition capability, the next implementation step must be **Task 2A - Nutrition-scope cleanup and migration** before Task 3.

Task 2A must remove or safely deprecate the no-longer-required fields, UI questions, validation requirements, API requirements, and planner assumptions without damaging existing user data or unrelated functionality.

All migrations must be backward compatible.

---

## 3. Mandatory staged execution

Do not implement the entire project in one run.

Implement exactly one task at a time in the order defined in **Section 48: Staged implementation tasks**.

### Before starting any task

1. Inspect the repository, current branch, remotes, and working tree.
2. Read `AGENTS.md`, the root README, and all relevant documentation.
3. Inspect current backend and frontend patterns before proposing new structure.
4. Fetch the latest remote state without overwriting uncommitted work.
5. Create or reuse the dedicated feature branch.
6. Never commit directly to `main`.
7. Never force-push.
8. Never discard or rewrite unrelated user changes.
9. Do not silently invent product rules.
10. Follow already approved Task 0 scientific and safety policies unless this rewritten specification explicitly changes product scope.

### After every task

For each task:

1. Implement only that task.
2. Add required database migrations.
3. Add meaningful unit, integration, and frontend tests relevant to that task.
4. Update relevant documentation.
5. Run every check affected by the task.
6. Review the complete diff.
7. Create focused commits.
8. Push the dedicated branch when credentials are available.
9. Report exact results.
10. Stop and wait for explicit user approval.

Do not automatically begin the next task.

### Required task report

After every task, report:

- Task number and title
- What was implemented
- Architectural decisions
- Created files
- Modified files
- Database migrations
- Tests added or updated
- Commands executed
- Exact result of each command
- Commit SHA
- Pushed branch
- Assumptions
- Known limitations
- Pre-existing failures
- Decisions requiring user approval before the next task

Never claim that a command succeeded unless it actually succeeded.

---

## 4. Repository-first implementation

Before changing production code, inspect and follow the existing architecture.

### Backend areas to inspect

- `profile`
- `workouts`
- `workout_cycles`
- `training_templates`
- `body_analysis`
- Existing body-analysis review workflow
- Existing physician or coach concepts
- `admin`
- Authentication and ownership dependencies
- SQLAlchemy models and repository conventions
- Pydantic schemas
- Services and repositories
- Domain exceptions
- Background-job infrastructure
- File upload and storage infrastructure
- Existing AI-provider and model-settings infrastructure
- Alembic environment and migration history
- Existing tests

### Frontend areas to inspect

- Routing and route guards
- Authentication
- Shared API client
- `features/profile`
- `features/workouts`
- `features/landing`
- Dashboard
- Admin features
- Existing AI settings pages
- Upload and image-preview components
- i18n
- RTL handling
- Form validation
- Existing charting library, if any
- Existing tests

Extend the current architecture instead of introducing an unrelated style.

Do not broadly rewrite workout functionality.

Do not break:

- Existing users
- Authentication
- Workout generation
- Workout history
- Body analysis
- Body photos
- Admin pages
- Existing review workflows
- Existing AI settings
- Existing API contracts unless a backward-compatible replacement is provided

Schema changes affecting existing users must use backward-compatible migrations.

---

## 5. Product vision

Fitsho must feel like one coach that understands training, nutrition, progress, medical constraints, food preferences, and budget.

Nutrition plans must be based on:

- Age
- Sex used for validated metabolic equations
- Height
- Current weight
- Reliable body-composition data when available
- Primary goal
- Daily non-exercise activity
- Structured exercise
- Training type, frequency, duration, and reliable intensity data
- Estimated energy requirements
- Protein, carbohydrate, fat, fibre, and diet-quality targets
- Versioned age-, sex-, and life-stage-appropriate micronutrient reference targets
- Micronutrient data completeness and confidence
- Allergies and intolerances
- User-declared diseases
- Current medications
- Medical restrictions
- Relevant symptoms covered by approved policy
- Physician-prescribed dietary restrictions
- Hard food exclusions required for safety
- Two ordinary food-preference questions only: foods the user likes and foods the user dislikes
- User-selected daily meal structure: number of main meals and number of snacks
- Individual monthly food budget
- Verified food-composition data, including core micronutrients where sufficiently reliable
- Fresh and traceable food-price data
- Versioned scientific and safety policies
- Actual or approximate adherence data from previous weeks
- Mandatory physician approval before plan activation
- Secure laboratory documents when available or requested
- Physician-managed supplement orders and follow-up when clinically appropriate

Cost and personal preference are important, but they are secondary to safety and configured nutritional adequacy.

The planner must never choose a food only because it is cheap.

---

## 6. Goals supported by the scientific engine

The goal model must support existing repository-compatible goal values and, at minimum, concepts equivalent to:

```text
WEIGHT_LOSS
WEIGHT_GAIN
MUSCLE_GAIN
BODY_RECOMPOSITION
FAT_LOSS
MAINTENANCE
```

Where repository naming already exists, extend or map it rather than creating incompatible duplicate concepts.

Goal meaning must be explicit:

- `WEIGHT_LOSS`: reduce body weight under an approved energy-deficit policy.
- `WEIGHT_GAIN`: increase body weight under an approved energy-surplus policy.
- `MUSCLE_GAIN`: prioritize muscle gain with an appropriate energy and protein strategy.
- `BODY_RECOMPOSITION`: pursue fat reduction with muscle preservation or gain where appropriate, using approved policy and training context.
- `FAT_LOSS`: prioritize fat reduction while preserving lean mass as much as reasonably possible.
- `MAINTENANCE`: maintain body weight and nutritional adequacy.

Do not hardcode arbitrary deficit, surplus, protein, or rate-of-change values in business logic. These must come from versioned approved scientific policy.

Each supported goal must map through a versioned `GoalPolicy` to its energy-direction/range, protein strategy, and any applicable rate-of-change logic. Overlapping labels such as `WEIGHT_LOSS` versus `FAT_LOSS`, or `WEIGHT_GAIN` versus `MUSCLE_GAIN`, must not rely on name interpretation inside planner code.

The engine must not treat all users with the same goal identically. It must consider age, sex, height, weight, activity, training, body composition when reliable, medical restrictions, and data quality.

Do not assume that micronutrient requirements scale directly with body weight. For most micronutrients, select the applicable authoritative reference by age, sex, supported life stage, and explicitly known evidence-based modifiers. Use weight only when an approved nutrient-specific policy explicitly requires it.

---

## 7. Scientific planning hierarchy

Keep **planner feasibility**, **planner optimization**, and **post-planning lifecycle approval** separate. Do not mix physician workflow state into food-ranking logic.

### Planner hard feasibility constraints

The planner must never violate:

1. Age eligibility
2. Safety and medical-condition policy
3. Allergy and hard-exclusion safety for planning
4. Configured nutritional safety floors
5. Applicable nutrient-specific upper bounds, CDRR/medical restrictions, and other hard medical limits
6. Protein minimum and other macronutrient minimums explicitly classified as hard by approved policy
7. User-selected meal-slot count and meal-role eligibility
8. Mandatory food/nutrient data required for safe calculation
9. Valid price requirements for the selected price mode
10. `STRICT` budget when the user selected strict budget mode

### Planner optimization priorities

Among feasible plans, optimize according to versioned policy for:

1. Goal-appropriate calories
2. Preferred protein
3. Fat and carbohydrate ranges
4. Fibre and configured diet-quality limits
5. Core micronutrient adequacy
6. User-selected meal distribution and portion feasibility
7. `FLEXIBLE` budget target and cost efficiency
8. Food likes and dislikes
9. Variety and repetition control
10. Prior adherence and meal feedback

The exact scoring weights and tolerances must remain versioned. A soft target must never override a hard feasibility constraint.

### Post-planning lifecycle gate

Mandatory physician review is **not** a food-selection objective. After a safe feasible draft is generated, the separate lifecycle workflow determines review, approval, activation, and the physician-approved badge.

Evaluate adequacy at meal, day, and week levels.

Calories, macronutrients, hard safety limits, and medical constraints may require day-level validation. Most micronutrient adequacy should be evaluated primarily over an approved rolling or weekly-average window unless a nutrient-specific policy requires stricter daily handling.

For any micronutrient where a poor individual day must be guarded against, the versioned micronutrient policy must define the applicable daily guard or floor. Do not use an undefined phrase such as `seriously inadequate` as executable validation logic, and do not invent a universal daily percentage for every micronutrient.

---

## 8. Unified product mode

Add or preserve a product-mode preference:

```text
TRAINING
NUTRITION
BOTH
```

### Existing users

Existing users with a completed training profile must remain compatible with `TRAINING` migration behavior implemented previously.

Existing workout functionality must continue to work unchanged.

### New users

New users must explicitly choose a product mode.

Do not preselect a mode.

The first required choice after Get Started remains conceptually:

> بیشتر در چه زمینه‌ای به کمک نیاز داری؟

Show three selectable cards:

**تمرین**  
برنامه شخصی براساس بدن، هدف، سطح، زمان و تجهیزات

**تغذیه**  
برنامه غذایی متناسب با هدف، نیاز بدن، محدودیت‌های پزشکی، مواد غذایی و بودجه

**تمرین و تغذیه**  
یک برنامه هماهنگ برای نتیجه بهتر

Mark the third option as Fitsho's recommendation, but do not preselect or force it.

### Changing mode

Users must be able to change mode later.

When a capability is enabled later, ask only for missing capability-specific information.

Disabling a capability must not delete historical plans, logs, reviews, photos, or profile information.

---

## 9. One unified profile

Fitsho must present one unified profile and one coordinated onboarding flow.

Do not create disconnected training and nutrition profiles containing duplicate body information.

Internally, normalized components are preferred, such as:

- Shared `UserProfile`
- Training-specific profile component
- Nutrition-specific profile component
- Medical and safety component
- Food-preference and exclusion components
- Structured-exercise component

Requirements:

- The user sees one profile.
- Shared information is entered once.
- Shared fields have one source of truth.
- Training and nutrition reuse the same birth date, age, sex, height, weight, and primary goal.
- The database must not become one extremely large table with unrelated nullable fields.

Capability-aware completion states should include concepts equivalent to:

```text
PRODUCT_MODE_NOT_SELECTED
SHARED_PROFILE_INCOMPLETE
TRAINING_ONBOARDING_INCOMPLETE
NUTRITION_ONBOARDING_INCOMPLETE
MEDICAL_REVIEW_INFORMATION_INCOMPLETE
TRAINING_READY
NUTRITION_DRAFT_READY
NUTRITION_PENDING_REVIEW
NUTRITION_READY
BOTH_READY
```

Use these meanings consistently:

- `NUTRITION_DRAFT_READY`: a successful safe draft exists but the review-request transaction has not yet completed. Treat this as transitional/internal when possible; do not use it to imply clinical readiness.
- `NUTRITION_PENDING_REVIEW`: the current Nutrition revision is user-visible and has a non-approved physician review state such as pending, in review, awaiting labs, or changes requested.
- `NUTRITION_READY`: the user has a physician-approved Nutrition revision that is `ACTIVE` for the current date.
- `BOTH_READY`: Training is ready and Nutrition is `NUTRITION_READY`.

Use capability-specific route guards and derive readiness from authoritative plan/review state rather than maintaining an unrelated drifting flag.

---

## 10. Conditional guided onboarding

The onboarding must behave like a guided conversation with a Fitsho coach.

Do not show one long form.

Group related questions into focused steps.

### Required ordering

1. Product mode
2. Birth date and age eligibility
3. Primary goal
4. Core body information
5. Early safety and medical-condition screening, including allergies, intolerances, dangerous-reaction history, current medications/conditions, physician-prescribed restrictions, hard food exclusions, and — when enabled micronutrient policy requires them — structured dietary pattern and current smoking status
6. Daily non-exercise activity
7. Structured exercise
8. Individual monthly food budget
9. Main-meal count question: `معمولاً در روز چند وعده اصلی غذا می‌خوری؟`
10. Snack count question: `معمولاً در روز چند میان‌وعده می‌خوری؟`
11. Food preference question: `چه غذاهایی را دوست داری؟`
12. Food preference question: `چه غذاهایی را دوست نداری؟`
13. Safety/restriction review: show the allergies, intolerances, physician-prescribed restrictions, dietary pattern/smoking inputs when applicable, and hard exclusions already captured in Step 5 for confirmation or correction; do not ask the same questionnaire a second time
14. Review and confirmation

When structured dietary pattern or current smoking status is required by an enabled micronutrient policy, collect it inside Step 5 with an explicit `UNKNOWN`/decline option. These are scientific/health inputs, not ordinary food-preference questions. Do not infer either value from liked/disliked foods.

There must be no additional ordinary food-preference questionnaire during onboarding. The two meal-structure questions are not preference questions; they are direct planner inputs.

### Required meal-structure questions

Ask exactly these two meal-structure questions during Nutrition onboarding:

**Question 1**

`معمولاً در روز چند وعده اصلی غذا می‌خوری؟`

Options:

```text
2 وعده
3 وعده
4 وعده یا بیشتر
```

Store a typed value equivalent to:

```text
TWO_MAIN_MEALS
THREE_MAIN_MEALS
FOUR_OR_MORE_MAIN_MEALS
```

**Question 2**

`معمولاً در روز چند میان‌وعده می‌خوری؟`

Options:

```text
هیچ‌کدام
1 میان‌وعده
2 میان‌وعده
3 میان‌وعده یا بیشتر
```

Store a typed value equivalent to:

```text
ZERO_SNACKS
ONE_SNACK
TWO_SNACKS
THREE_OR_MORE_SNACKS
```

For open-ended options, do not invent an exact hidden count above the displayed minimum. The planner may use the minimum represented count as the generated-plan slot count (`4` main meals or `3` snacks) unless a future explicitly approved UX collects a more exact count. Persist both the selected bucket and the effective slot count used for the plan snapshot.

These answers must affect plan generation. They are not display-only metadata.

Variety and repetition must use sensible defaults and later meal feedback rather than additional onboarding questions.

If early screening determines that the user requires manual-only review or is not eligible, do not waste the user's time with unnecessary later questions. Save allowed data and direct the user to the correct flow.

Show short deterministic feedback after important answers, for example:

- `عالی، هدفت کاهش چربی با حفظ عضله است.`
- `فعالیت روزانه و تمرینت را جداگانه محاسبه می‌کنیم تا تخمین انرژی دقیق‌تر باشد.`
- `بودجه هفتگی از بودجه ماهانه محاسبه می‌شود و برنامه سعی می‌کند تا حد ممکن به هدف تغذیه‌ای ترجیحی نزدیک شود.`
- `تعداد وعده‌های اصلی و میان‌وعده‌ها را در تقسیم کالری و مواد مغذی برنامه لحاظ می‌کنیم.`
- `به‌دلیل شرایط پزشکی ثبت‌شده، برنامه قبل از فعال‌شدن باید توسط پزشک فیتشو بررسی شود.`

Do not call OpenRouter or any AI API during normal onboarding.

### Conditional fields

#### Shared fields

Ask once:

- Display name
- Birth date
- Sex required by selected equations
- Height
- Current weight
- Relevant body measurements when supported
- Primary goal
- Daily non-exercise activity
- Shared medical and safety information

#### Training mode

Ask existing training-specific fields. Do not ask nutrition-specific questions.

#### Nutrition mode

Ask nutrition-specific fields and the minimum structured-exercise information needed for energy estimation.

Do not require training-only fields.

#### Both mode

- Ask shared fields once.
- Ask the training branch.
- Ask the nutrition branch.
- Reuse training information in nutrition calculations.
- Do not ask duplicate exercise questions.

---

## 11. Age eligibility

Fitsho does not support users under 18 in this MVP.

A birth date representing an age under 18 must be rejected.

Requirements:

- Return a stable domain error such as `AGE_NOT_SUPPORTED`.
- Do not complete the profile.
- Do not generate a training plan.
- Do not generate a nutrition plan.
- Do not create a photo-estimation request.
- Do not create a supplement recommendation.
- Display a calm Persian explanation.
- Do not treat an under-18 user as an ordinary safety-blocked adult profile.

Preserve the established upper-age policy unless repository inspection justifies a documented and explicitly approved change.

---

## 12. Early safety and medical-condition screening

Safety screening must occur early in onboarding, before plan generation, before physician approval, and before activation.

The user must be able to declare:

- Diagnosed diseases
- Current medications
- Allergies
- Intolerances
- History of dangerous food reactions
- Pregnancy or breastfeeding
- Eating-disorder diagnosis or active symptoms
- Kidney disease or dialysis
- Liver disease
- Diabetes type and treatment
- Blood-pressure conditions
- Lipid disorders
- Gastrointestinal conditions
- Physician-prescribed dietary restrictions
- Other relevant conditions supported by policy
- Optional physician notes
- Laboratory documents uploaded through the secure laboratory-record workflow when available

Do not diagnose a condition from onboarding answers.

Create versioned condition policies with outcomes equivalent to:

```text
AUTOMATIC_DRAFT_PHYSICIAN_REVIEW_REQUIRED
PHYSICIAN_MANUAL_PLAN_REQUIRED
UNSUPPORTED_OR_HARD_BLOCKED
```

If the existing repository already contains a `STANDARD_AUTOMATIC` value for backward compatibility, do not destructively rewrite historical records. Map new Nutrition behavior so that even a standard-risk user receives only an automatically generated **draft** and still requires physician approval before activation.

### Automatic draft with mandatory physician review

This is the default supported Nutrition flow.

The deterministic engine may generate a draft, but:

- The plan cannot become active automatically.
- The complete generated draft must become immediately visible to the owning user after successful generation and deterministic validation.
- User visibility must not depend on physician approval. `PENDING_PHYSICIAN_REVIEW`, `PHYSICIAN_REVIEW_IN_PROGRESS`, and `AWAITING_LAB_INFORMATION` are approval/workflow states, not visibility locks.
- Before approval, the user may view the full plan, meals, snacks, quantities, nutrient totals, micronutrient analysis, budget, shopping list, and current physician-review status.
- Before approval, the plan must be clearly labeled `PENDING_PHYSICIAN_REVIEW` or the applicable review state and must not show the green physician-approved badge/checkmark.
- The plan cannot be presented as physician-approved before a real physician action.
- The exact plan revision must be submitted to the physician queue.
- The physician may approve, reject, request changes, request laboratory information, or edit the structured plan.
- If the physician edits foods, quantities, targets, or restrictions, Fitsho must create a new immutable revision and rerun deterministic validation.
- After physician approval, the user must see the approved revision, green physician-approval badge/checkmark, approval metadata, user-visible physician notes, physician-added supplement orders, and a clear summary of changes from the originally generated revision when changes exist.

### Physician manual plan required

Do not create or activate an ordinary generic plan when approved policy says manual physician planning is required. A physician must create or substantially edit the plan before it can be approved and activated.

### Unsupported or hard blocked

Do not generate or activate a plan. Persist safe profile data, return a structured result, and show a respectful explanation.

Pregnancy, breastfeeding, diagnosed or active eating disorders, dialysis, severe unstable disease, or another condition classified as unsupported by approved policy must not receive an ordinary automatic plan unless future approved policy explicitly adds a safe supported pathway.

Ordinary allergies and intolerances that can be represented safely must become hard ingredient exclusions for **planning and recommendation**.

An excluded ingredient must never appear in:

- Generated meals
- Ingredient substitutions
- Meal substitutions
- Shopping lists derived from the plan
- Planner-generated quick-add suggestions
- Supplement products containing the allergen

Actual-consumption logging is different from planning. If the user reports or confirms that they actually consumed an excluded/allergenic food, Fitsho may record that reality in calorie history with a prominent safety warning and without treating the food as planner-eligible. Photo logging may therefore map and record a user-confirmed allergenic food as actual intake; it must not silently recommend, normalize, or insert that food into the plan.

Mandatory physician review is an activation gate for every Nutrition plan, but it does not weaken deterministic safety rules. A physician edit must never bypass allergy, ownership, database-integrity, or configured hard-safety validation.

## 13. Nutrition profile

Create or preserve a nutrition-specific component inside the unified profile.

Support at least:

- User ID
- Nutrition onboarding status
- Individual monthly food budget
- Currency fixed to `IRR`
- Strict or flexible budget
- Main-meal count selection
- Snack count selection
- Effective main-meal slot count used by the planner
- Effective snack slot count used by the planner
- Preferred plan start day
- Foods the user likes
- Foods the user dislikes
- Allergies
- Intolerances
- Structured dietary pattern when needed by nutrition policy, such as omnivore, vegetarian, vegan, or another supported restricted pattern
- Smoking status when an approved nutrient policy requires it for a documented modifier
- Religious or cultural exclusions
- Work-day and shift context when needed for meal timing
- Medical-condition and safety answers
- Mandatory physician-review state for Nutrition plans
- Whether notifications for daily quick check-in are enabled
- Preferred quick check-in time
- Created and updated timestamps

### Meal structure as a first-class nutrition input

The meal structure is not cooking metadata and must remain in Nutrition. It tells the planner how many substantial meals and light snack slots to create after the scientific target engine has calculated the user's daily requirements.

The scientific target engine must calculate daily targets independently of meal count. The meal-distribution layer runs afterward and distributes those targets across the user-selected structure.

The selected meal structure must be included in:

- Nutrition onboarding completion
- Nutrition profile API
- Planner input snapshot
- Weekly-plan snapshot
- Regeneration logic
- Plan editing validation where slot count changes are supported later
- Tests

Ordinary preference onboarding must expose only these two preference questions:

```text
LIKED_FOODS
DISLIKED_FOODS
```

Structured dietary pattern and smoking status belong to health/nutrition context, not to ordinary food-preference onboarding.

Whenever possible, likes and dislikes should be selected through catalogue search/autocomplete and persisted as canonical `food_id` references. Free-text aliases may be resolved only through deterministic catalogue aliases/mappings. Preserve unresolved text separately and do not let unresolved free text affect planner scoring until it is deterministically mapped.

Do not introduce additional ordinary preference questions unless later explicitly approved.

Use relational models and enums where filtering, ownership, or validation is required.

Flexible collections may use JSON only when strictly validated, bounded, and consistent with repository patterns.

Do not store the entire profile in one unvalidated JSON field.

---

## 14. Main meals, snacks, and nutrient distribution

Fitsho Nutrition must distinguish two nutrition slot roles:

```text
MAIN_MEAL
SNACK
```

This distinction is about nutritional role and portion structure. It must not contain cooking instructions, preparation time, equipment, recipes, batch-cooking logic, or other Cooking-domain behavior.

### Main meals

A `MAIN_MEAL` is a substantial meal intended to carry a meaningful share of the day's energy, protein, carbohydrates, fats, fibre, and other nutrient targets.

Main-meal compositions may include verified combinations such as:

- Chicken, turkey, red meat, fish, or another compatible substantial protein source
- Eggs and other substantial breakfast-style protein sources
- Rice, potatoes, bread, grains, or another compatible staple carbohydrate source
- Vegetables, dairy, fats, or other verified foods when useful to complete the nutritional target
- Medically and personally compatible plant-protein alternatives such as legumes or soy when appropriate

Examples are illustrative categories, not mandatory recipes. The planner selects exact foods and quantities from verified catalogue records.

A lunch/dinner-style main meal should normally contain a substantial compatible protein anchor and, when required by the daily carbohydrate allocation, a staple carbohydrate anchor. A breakfast-style main meal may use eggs, dairy, bread/grains, fruit, or other verified substantial breakfast foods while still carrying a meaningful share of the day's targets. The planner must not force meat or fish into breakfast merely to satisfy the `MAIN_MEAL` role.

Foods that form a substantial plate such as chicken/meat/fish with rice or potatoes belong to main-meal generation, not snack generation.

### Snacks

A `SNACK` is a lighter eating occasion used to distribute energy and nutrients, improve practical adherence, or close a nutrient gap without turning the snack into another full main meal.

Snack candidates may include verified foods such as:

- Fruit
- Dairy foods where compatible
- Nuts and seeds
- Verified ordinary food products such as protein bars when represented in the food catalogue with reliable nutrition data
- Other light snack-category foods approved in the catalogue

Do not place substantial chicken, red-meat, fish, rice-and-protein plates, or similar main-meal compositions into a `SNACK` slot.

A protein bar is treated as food only when it is catalogued as an ordinary food product with verified composition data. Protein powders or supplement products remain governed by the supplement workflow.

### Distribution sequence

The engine must use this order:

1. Calculate BMR and TDEE.
2. Calculate goal-adjusted daily calorie target.
3. Calculate daily protein, carbohydrate, fat, fibre, and diet-quality targets or limits.
4. Read the user-selected main-meal count and snack count.
5. Create the required `MAIN_MEAL` and `SNACK` slots.
6. Allocate meaningful portions of daily energy and nutrients across the slots according to versioned meal-distribution policy.
7. Generate candidate foods appropriate for each slot role.
8. Optimize exact food quantities across all slots together.
9. Validate meal, day, and week totals.
10. Validate cost and other hard constraints.

Daily nutritional adequacy has priority over making every meal numerically identical. Do not blindly divide calories or protein equally across all slots.

Main meals should generally carry the larger share of substantial protein and staple-food allocation; snacks should complement the day and may help close calorie, protein, fibre, fruit, dairy, or other approved gaps. Exact distribution rules and tolerances must come from versioned approved policy, not hardcoded magic percentages.

If a user selects zero snacks, the planner must not create snack slots merely to make optimization easier. If the user selects two main meals, the planner must generate two main-meal slots and adapt exact portions accordingly, subject to safety and feasibility.

Use a versioned `PortionFeasibilityPolicy` for practical per-slot bounds or warnings such as implausibly large meal energy/quantity, implausibly small meals, or another supported adherence-feasibility rule. Do not hardcode one universal gram or calorie limit for every user and meal type.

If the selected meal structure cannot realize the preferred targets within approved portion-feasibility bounds, do not silently invent extra meal slots. Preserve the scientific target, return the closest safe feasible result, and show a structured `MEAL_STRUCTURE_FEASIBILITY_WARNING` or request that the user explicitly change meal structure when policy requires it.

The planner must never lower scientific daily targets merely because the user selected fewer meal slots. If the selected structure makes the preferred target difficult to realize under current constraints, preserve the target, find the closest safe feasible distribution, and explain the gap.

Persist in every plan snapshot:

- Selected main-meal bucket
- Selected snack bucket
- Effective main-meal slot count
- Effective snack slot count
- Meal-distribution policy version
- Per-slot role (`MAIN_MEAL` or `SNACK`)
- Per-slot nutrient totals

---

## 15. Individual budget and cost meaning

The budget belongs only to the authenticated user.

Use a field equivalent to:

`individual_monthly_food_budget_irr`

Do not add household-budget division in this scope.

All money values must:

- Use IRR
- Be stored as integer rials or exact SQL numeric values
- Never use binary floating point
- Use integer or `Decimal` arithmetic
- Be deterministic
- Be non-negative
- Have reasonable input limits

Convert monthly budget into a normalized seven-day allowance using:

```text
normalized_weekly_budget_allowance_irr = floor(monthly_budget_irr * 12 / 52)
```

This is a deterministic annualized budget policy, not a calendar-exact statement of what the user can spend in a specific 28-, 29-, 30-, or 31-day month. Persist the formula/policy version in the plan snapshot.

The UI must clearly display:

> مبلغ به ریال

Never silently display tomans.

### Budget mode semantics

Use an explicit budget mode equivalent to:

```text
STRICT
FLEXIBLE
```

- `STRICT`: the normalized weekly allowance is a hard feasibility ceiling. A plan above it is not feasible.
- `FLEXIBLE`: budget is a soft optimization target. The planner may exceed it only within a versioned configured excess cap, must show the exact overage, and must never present the result as being within budget.

Use `STRICT` as the safe default when no explicit budget-mode preference has been selected. `FLEXIBLE` should be an explicit optional budget setting rather than another mandatory onboarding question.

Do not let a preferred protein, micronutrient, variety, or convenience target override a `STRICT` budget ceiling.

### Cost semantics

Fitsho must calculate the cost of the exact amount required by the plan.

Example:

- The plan requires `2.3 kg` of chicken breast across the week.
- The selected normalized price is `X IRR per gram`.
- Fitsho displays the nutritional contribution of that amount and its estimated cost.

Keep two cost concepts separate:

- `planned_consumption_cost`: the normalized cost of the exact quantity used by the nutrition plan.
- `expected_purchase_outlay`: optional estimated cash outlay when reliable minimum-purchase/package metadata proves that the user cannot buy exactly the planned quantity.

`planned_consumption_cost` remains the canonical nutrition-plan cost. `expected_purchase_outlay` must be shown only when reliable purchase-unit metadata exists; otherwise return it as unknown rather than fabricating package behavior.

Do not turn the Nutrition Core into a package-count shopping recommender. Do not round required nutrition quantities merely for display. A provider quote may originate from a package, but the plan must continue to show the exact quantity consumed and its normalized cost.

---

## 16. Separate daily activity and structured exercise

Store daily non-exercise activity and structured exercise separately.

### Daily activity

Use a typed enum equivalent to:

```text
MOSTLY_SEATED
LIGHTLY_ACTIVE
MODERATELY_ACTIVE
HIGHLY_ACTIVE
```

This represents movement outside deliberate exercise.

### Structured exercise

Track separately:

- Exercise type
- Days per week
- Duration
- Reliable intensity
- Source of information

Sources may include:

- User-provided data
- Training profile
- Active Fitsho workout plan
- Versioned internal estimate

For `BOTH`, use the best available structured-exercise source in this precedence order:

1. Active Fitsho workout plan when current and applicable
2. Completed training profile with sufficient frequency/duration/intensity information
3. Minimum structured-exercise inputs collected for Nutrition
4. A versioned conservative internal estimate only when policy permits, clearly marked lower confidence

Nutrition generation must not deadlock merely because a `BOTH` user does not yet have an active workout plan. Persist which source was used.

For `NUTRITION`, ask only the minimum exercise questions needed.

### TDEE strategy

Use one coherent method:

1. Calculate BMR.
2. Apply a daily-activity component that excludes structured exercise.
3. Estimate structured-exercise energy separately.
4. Convert weekly structured-exercise energy to a daily average.
5. Add it to the non-exercise estimate.

Conceptually:

```text
estimated_tdee = non_exercise_energy_estimate + average_daily_training_energy
```

Do not use an activity factor that already includes training and then add exercise again.

Persist both components separately.

Do not present either value as an exact measurement.

---

## 17. Versioned scientific, safety, and planning policies

Create versioned policy concepts equivalent to:

- `NutritionPolicy`
- `NutritionPolicyVersion`
- `SafetyDecision`
- `SafetyReason`
- `MedicalConditionPolicy`
- `EstimateMethod`
- `GoalPolicy`
- `MacroTargetPolicy`
- `MealDistributionPolicy`
- `PortionFeasibilityPolicy`
- `DietQualityPolicy`
- `MicronutrientReferencePolicy`
- `MicronutrientOptimizationPolicy`
- `MicronutrientRepairPolicy`
- `BudgetPolicy`
- `PriceFreshnessPolicy`
- `PhotoEstimationPolicy`
- `AdherencePolicy`
- `SupplementPolicy`
- `PlannerVersion`

Do not scatter formulas, limits, tolerances, and scoring weights as magic numbers.

Every generated plan must persist:

- Policy version
- Formula version
- Planner version
- Food-data versions
- Price-selection version
- Adherence-policy version
- Medical-condition-policy version
- Micronutrient-reference-policy version
- Micronutrient-optimization-policy version
- Micronutrient-repair-policy version

The scientific-policy table approved during Task 0 remains authoritative for previously approved rules. Because micronutrient optimization is a new product requirement added after Tasks 0–2, its reference tables, source versions, nutrient semantics, and planner tolerances must be explicitly documented and approved before micronutrient-aware production planning is activated.

### Authoritative micronutrient source hierarchy

Use the following source hierarchy:

1. **National Academies of Sciences, Engineering, and Medicine (NASEM) Dietary Reference Intakes (DRIs)** for RDA, AI, EAR, UL, CDRR, age/sex/life-stage groups, and nutrient-specific reference semantics.
2. **NIH Office of Dietary Supplements (ODS) Health Professional Fact Sheets** to cross-check current DRI values, units, bioavailability notes, nutrient-specific upper-limit scope, risk groups, and clinically important interpretation caveats.
3. **USDA FoodData Central (FDC)** for food-composition values and provenance. USDA food-composition data must not be used as the source of human requirement targets.
4. Approved medical-condition guidelines may override general healthy-population references only through versioned `MedicalConditionPolicy` and physician-review rules.

**Source research date:** 2026-08-08.

Primary references:

- NASEM DRI collection: https://nap.nationalacademies.org/collection/57/dietary-reference-intakes
- NASEM Dietary Reference Intakes for Sodium and Potassium (2019): https://nap.nationalacademies.org/catalog/25353/dietary-reference-intakes-for-sodium-and-potassium
- NIH ODS Calcium: https://ods.od.nih.gov/factsheets/Calcium-HealthProfessional/
- NIH ODS Potassium: https://ods.od.nih.gov/factsheets/Potassium-HealthProfessional/
- NIH ODS Magnesium: https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/
- NIH ODS Iron: https://ods.od.nih.gov/factsheets/Iron-HealthProfessional/
- NIH ODS Zinc: https://ods.od.nih.gov/factsheets/Zinc-HealthProfessional/
- NIH ODS Vitamin C: https://ods.od.nih.gov/factsheets/VitaminC-HealthProfessional/
- NIH ODS Vitamin D: https://ods.od.nih.gov/factsheets/VitaminD-HealthProfessional/
- NIH ODS Vitamin B12: https://ods.od.nih.gov/factsheets/VitaminB12-HealthProfessional/
- NIH ODS Folate: https://ods.od.nih.gov/factsheets/Folate-HealthProfessional/
- NIH ODS Vitamin A: https://ods.od.nih.gov/factsheets/VitaminA-HealthProfessional/
- NIH ODS Vitamin E: https://ods.od.nih.gov/factsheets/VitaminE-HealthProfessional/
- NIH ODS Vitamin K: https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/
- NIH ODS Vitamin B6: https://ods.od.nih.gov/factsheets/VitaminB6-HealthProfessional/
- USDA FoodData Central API and documentation: https://fdc.nal.usda.gov/api-guide/ and https://fdc.nal.usda.gov/data-documentation/

Store source URL or source identifier, source publication/update date when available, access date, policy version, and the exact unit semantics with every imported or seeded reference row.

### DRI semantics Fitsho must preserve

Do not collapse all reference values into a generic `minimum` or `maximum`. Support at least:

```text
RDA
AI
EAR
UL
CDRR
MEDICAL_OVERRIDE
```

Rules:

- For ordinary individual meal planning, use the applicable **RDA** as the preferred adequacy target when an RDA exists.
- When an RDA does not exist and an **AI** exists, use the AI as the preferred adequacy reference and label it as AI rather than RDA.
- Do not use **EAR** as a personal hard minimum or as proof that an individual is deficient.
- Treat **UL** as a safety ceiling only within the source scope to which that UL applies; a UL is not an intake goal.
- Treat **CDRR** according to its nutrient-specific meaning. In particular, sodium CDRR behavior must not be incorrectly represented as a generic toxicity UL.
- If no authoritative UL or CDRR exists for a nutrient in the apparently healthy population, do not invent one.
- General healthy-population DRI values must not override a versioned medical restriction.

### Required micronutrient policy model

Create normalized versioned reference rows supporting fields equivalent to:

```text
nutrient_code
reference_kind
target_value
unit
age_min
age_max
sex
life_stage
dietary_pattern_modifier
modifier_multiplier_or_delta
upper_limit_scope
aggregation_window
source_organization
source_reference
source_date
access_date
policy_version
notes
```

Do not scatter numeric DRI values directly through planner functions. The planner must query a versioned reference policy and persist the exact selected reference rows in the plan snapshot.

The `life_stage` field keeps the reference schema extensible. A life-stage reference row does not automatically mean that the MVP supports plan generation for that life stage; current safety policy may still classify pregnancy, breastfeeding, or another stage as unsupported until an explicitly approved pathway exists.

### Core micronutrient set

The architecture must support an extensible nutrient registry. For the first production micronutrient-aware planner, require reliable handling for at least:

**Core minerals and electrolytes**

- Calcium
- Potassium
- Magnesium
- Iron
- Zinc
- Sodium

**Core vitamins**

- Vitamin C
- Vitamin D
- Vitamin B12
- Folate / vitamin B9 using dietary folate equivalents where required

Also support, when sufficiently reliable food-composition and policy data are available:

- Vitamin A using retinol activity equivalents where required
- Vitamin E using approved alpha-tocopherol units
- Vitamin K
- Thiamin / vitamin B1
- Riboflavin / vitamin B2
- Niacin / vitamin B3
- Vitamin B6
- Selenium
- Iodine
- Phosphorus

The registry must allow additional micronutrients later without redesigning the planner.

### Authoritative-value sanity checks

The complete reference table must be sourced from the authoritative references above, but implementation tests should include sanity checks for well-established adult values such as:

- Zinc RDA for adults 19+: 11 mg/day for males and 8 mg/day for females.
- Calcium RDA for adults 19–50: 1,000 mg/day; older adult reference values vary by age and sex.
- Potassium uses AI rather than RDA; the 2019 NASEM adult AI is 3,400 mg/day for males and 2,600 mg/day for females.
- Magnesium RDA varies by age and sex; for adults it is generally 310–420 mg/day.
- Iron RDA varies strongly by age, sex, and life stage; for ages 19–50 it is 8 mg/day for males and 18 mg/day for females under the standard mixed-diet reference.
- Vitamin C RDA for adults 19+ is 90 mg/day for males and 75 mg/day for females; the NASEM/NIH reference adds 35 mg/day for people who smoke when that modifier is explicitly known.
- Vitamin D RDA is 15 mcg/day (600 IU) for ages 19–70 and 20 mcg/day (800 IU) for adults older than 70 under the NASEM reference.
- Vitamin B12 RDA for adults is 2.4 mcg/day.
- Folate RDA for adults is 400 mcg DFE/day.
- For sodium, the 2019 NASEM adult AI is 1,500 mg/day, there is no established sodium UL in that report, and the adult CDRR recommends reducing intake when above 2,300 mg/day.

These sanity-check values are not a substitute for importing and versioning the full applicable reference tables.

### Nutrient-specific interpretation rules

The policy layer must support nutrient-specific semantics rather than assuming every nutrient behaves the same way. Examples:

- **Vitamin D:** dietary intake below RDA does not establish vitamin D deficiency because vitamin D status also depends on endogenous synthesis and is clinically assessed primarily with serum 25(OH)D. Fitsho may report dietary intake below the reference target but must not diagnose deficiency.
- **Potassium:** use AI for healthy-population adequacy. Do not invent a healthy-population UL. Kidney disease and relevant medications can require medical-policy overrides and review.
- **Sodium:** distinguish AI from CDRR. Do not label 2,300 mg/day as a toxicity UL.
- **Iron:** if an explicitly supported vegetarian dietary pattern is known, apply only an approved evidence-based bioavailability modifier. NIH ODS notes a 1.8-times iron requirement for vegetarian diets under the cited DRI interpretation. Do not infer vegetarian status from food likes/dislikes alone.
- **Vitamin C:** apply the smoking modifier only when smoking status is explicitly known through the approved Step 5 health/nutrition field. If that field is `UNKNOWN` or declined, do not apply the modifier and do not infer smoking status elsewhere.
- **Magnesium:** upper-limit scope differs by source form; do not reject high magnesium intake from ordinary food by incorrectly applying a supplemental-magnesium UL.
- **Folate:** preserve DFE semantics and distinguish naturally occurring food folate from synthetic folic acid when upper-limit logic depends on source.
- **Vitamin A:** preserve RAE semantics and distinguish preformed vitamin A from provitamin A carotenoids when upper-limit rules depend on form.

---

## 18. Scientific energy and nutrient engine

Implement a deterministic calculation engine independent of AI.

It must calculate or define targets, preferred ranges, and upper limits for:

- Estimated BMR
- Non-exercise daily energy expenditure
- Structured-exercise energy expenditure
- Estimated TDEE
- Goal-adjusted calorie target or range
- Protein minimum
- Protein preferred target
- Carbohydrate target or range
- Total-fat minimum
- Total-fat preferred range
- Fibre adequacy target and, only when explicitly defined by approved safety/medical policy, a hard fibre minimum
- Free-sugar maximum
- Added-sugar information and optional limit where reliable
- Saturated-fat maximum
- Trans-fat maximum
- Sodium AI/CDRR or other approved sodium reference semantics
- Selected core micronutrient RDA or AI targets
- Nutrient-specific ULs only where an authoritative UL exists and with the correct source scope
- Nutrient-specific medical overrides where approved

Use evidence-based adult formulas approved in Task 0.

Before meal planning, resolve the applicable micronutrient reference rows for the user from the versioned policy. Most micronutrient references must be selected by age, sex, supported life stage, dietary pattern modifier when explicitly known, and medical-policy override when applicable. Do not derive generic micronutrient targets from body weight unless the authoritative nutrient-specific policy explicitly does so.

Do not use one protein target for every user.

Protein targets must consider:

- Weight
- Goal
- Exercise type
- Training frequency
- Training status
- Energy deficit or surplus
- Reliable body-composition data
- Safety and medical restrictions

`MacroTargetPolicy` must also define the approved **protein reference-mass method** for cases such as high adiposity or unreliable/missing body-composition data. Do not blindly apply a grams-per-kilogram multiplier to total body weight when the approved policy calls for another evidence-based reference. If the required reference cannot be resolved safely, return lower confidence or require physician/policy review rather than inventing an adjusted-weight formula.

Resolve protein, fat, and carbohydrate ranges jointly or iteratively under the calorie target. Do not implement carbohydrate as an unchecked one-pass residual after fixing protein and fat if that can silently violate the approved carbohydrate or fat range.

Before returning targets, run a deterministic **macro-energy feasibility check**. Conceptually, the energy implied by every configured hard macronutrient minimum must fit inside the calorie target/range after applying the approved policy. If hard minimums conflict with the calorie target:

1. reduce or relax preferred targets first;
2. never silently reduce a hard safety/medical minimum;
3. allow the calorie target/range to move only when the versioned scientific policy explicitly permits that adjustment for the goal and safety context;
4. otherwise return a structured `TARGET_INFEASIBLE` generation outcome with the conflicting minima and reason codes instead of producing internally inconsistent targets.

The engine must explicitly distinguish:

1. `minimum_acceptable`
2. `preferred_target`
3. `planned_amount_under_current_constraints`

This distinction is central to Fitsho.

For example, if the preferred protein target is higher than what can be safely and realistically purchased under the budget, the system must not hide the gap. It must return the planned amount, difference from preferred, limiting constraints, and budget trade-off explanation.

Every target, including each micronutrient reference, must include:

- Nutrient code
- Reference kind (`RDA`, `AI`, `EAR`, `UL`, `CDRR`, or approved medical override)
- Target or limit value
- Unit and nutrient-form semantics
- Policy version
- Scientific source
- Applicable population
- Input snapshot
- Rounding rule
- Aggregation window
- Explanation metadata
- Confidence or data-quality status

The UI must use terms such as:

- `تخمین متابولیسم پایه`
- `تخمین مصرف انرژی روزانه`
- `هدف ترجیحی`
- `حداقل قابل قبول`
- `مقدار برنامه‌ریزی‌شده با بودجه فعلی`

Do not describe estimates as exact measurements.

---

## 19. Dietary-quality metrics and missing data

The planner, food catalogue, calorie counter, and history must support:

- Calories
- Protein
- Total carbohydrates
- Total fat
- Fibre
- Total sugars
- Added sugars
- Free sugars
- Saturated fat
- Trans fat
- Sodium
- Calcium
- Potassium
- Magnesium
- Iron
- Zinc
- Vitamin C
- Vitamin D
- Vitamin B12
- Folate / vitamin B9

Track additional registered micronutrients such as vitamins A, E, K, B1, B2, B3, B6, selenium, iodine, and phosphorus when both policy references and sufficiently reliable food-composition data are available.

Do not treat all carbohydrates, sugars, fats, or micronutrient reference types as equivalent.

### Micronutrient adequacy status

For each supported micronutrient, return structured status equivalent to:

```text
WITHIN_REFERENCE_TARGET
BELOW_REFERENCE_TARGET
ABOVE_APPLICABLE_LIMIT
MEDICAL_POLICY_RESTRICTED
DATA_INCOMPLETE
NOT_APPLICABLE
```

Do not use `DEFICIENT` as a diet-plan status. A dietary intake estimate below an RDA or AI is not itself a clinical diagnosis.

For each micronutrient report:

- Selected reference kind
- Selected reference value
- Planned daily average
- Planned weekly total or average as appropriate
- Percent of reference when mathematically meaningful
- Applicable upper-limit/CDRR status where relevant
- Data-completeness confidence
- Reason codes
- Whether a repair attempt changed the plan

Use weekly or rolling-average adequacy for most micronutrients, while still enforcing any daily hard medical or safety limits required by policy.

### Sugar distinctions

`total_sugars`, `added_sugars`, and `free_sugars` are different concepts.

Do not add `added_sugars` and `free_sugars` together.

Use free sugar as the main configured scientific limit when sufficiently reliable data exists.

Do not classify naturally occurring sugar in whole fruit or plain milk as free sugar.

### Missing data

A missing nutrient value must be unavailable, not zero.

Example:

```json
{
  "added_sugars_g": null
}
```

Do not infer unavailable added sugar, free sugar, trans fat, sodium, or micronutrients as zero.

A food with missing micronutrient data may still be usable when mandatory macro/safety data exists, but the planner must lower micronutrient-confidence for any affected plan and must not pretend the missing value is zero. A plan may only receive a high-confidence micronutrient adequacy status when the configured completeness threshold is satisfied.

Return warnings such as:

```text
FREE_SUGAR_DATA_INCOMPLETE
SODIUM_DATA_INCOMPLETE
MICRONUTRIENT_DATA_INCOMPLETE
MICRONUTRIENT_REFERENCE_UNAVAILABLE
MICRONUTRIENT_REPAIR_LIMIT_REACHED
PHOTO_PORTION_ESTIMATE_LOW_CONFIDENCE
```

---

## 20. Food catalogue

Create a normalized food and ingredient catalogue for nutrition planning.

Support:

- Canonical name
- Persian display name
- Optional English name
- Aliases and common misspellings
- Category
- Default unit
- Edible portion
- Canonical food form when required for accurate nutrition values
- Calories
- Protein
- Carbohydrates
- Total fat
- Fibre
- Total sugars
- Added sugars
- Free sugars
- Saturated fat
- Monounsaturated fat where available
- Polyunsaturated fat where available
- Trans fat
- Sodium
- Calcium
- Potassium
- Magnesium
- Iron
- Zinc
- Vitamin C
- Vitamin D
- Vitamin B12
- Folate / DFE-compatible data where available
- Additional registered micronutrients where reliable
- Nutrient form and unit metadata where required for correct interpretation
- Per-nutrient missing-data and confidence status
- Nutrition-data source
- Source reference ID
- Source access date
- Data version
- Verification status
- Active state
- Iranian serving units
- Gram, millilitre, and item conversions
- Optional provider package metadata used only for price normalization
- Allergen tags
- Dietary tags
- Nutrition slot-role tags or validated classification metadata sufficient to support:
  - `SUBSTANTIAL_MAIN_PROTEIN`
  - `MAIN_STAPLE_CARBOHYDRATE`
  - `SNACK_FOOD`
  - `FLEXIBLE_COMPLEMENT`
- Created and updated timestamps

When two food forms have materially different verified nutrient values, represent them as explicit verified catalogue records or explicit validated food forms. Do not infer one from the other using undocumented assumptions.

Store nutrient values consistently per 100 grams of edible portion, or another explicitly documented canonical basis when grams are invalid.

Use `Decimal` and SQL `Numeric`, not binary floating point.

For portions, calculate nutritional contributions proportionally from the canonical basis.

Never fabricate nutritional values.

Prefer authoritative composition data such as USDA FoodData Central where appropriate, while allowing verified Iranian or regional food-composition sources when their provenance, units, methods, and licensing are documented. Do not map an Iranian food to a superficially similar foreign food when the nutritional equivalence is uncertain.

FoodData Central is a food-composition source, not a human-requirement source.

If production-grade data cannot be completed:

- Build the complete import and validation mechanism.
- Add a limited verified dataset.
- Clearly distinguish production data from demo data.
- Never present demo data as authoritative.

Seed a useful verified subset of foods common in Iran.

### Food categories and economical source mix

The catalogue and planner must be able to work with verified foods from categories such as:

- Poultry
- Red meat
- Fish where available
- Eggs
- Dairy
- Legumes
- Soy products where available
- Grains
- Rice
- Bread
- Potatoes and other starchy foods
- Fruit
- Vegetables
- Nuts and seeds
- Oils and other dietary fat sources

This list is not permission to fabricate records. A food may be used only when verified data exists and all safety rules permit it.

Slot-role metadata must not be inferred from an LLM at plan-generation time. It must come from verified catalogue/admin data or deterministic versioned classification rules. Substantial poultry, red-meat, or fish portions and complete rice/potato-plus-primary-protein plates must be excluded from snack generation.

---

## 21. Structured meal composition

Meals must be structured combinations of verified foods and exact quantities.

A meal is a nutritional composition, not a free-text description.

Support:

- Meal name
- Meal type
- Nutrition slot role: `MAIN_MEAL` or `SNACK`
- Slot index within the day
- Food references
- Exact quantities
- Unit and serving conversion
- Nutritional totals
- Cost totals
- Allergen validation
- Dietary compatibility
- Source data versions

Do not store only free-text meal descriptions.

Example main meal:

```json
{
  "meal_type": "LUNCH",
  "slot_role": "MAIN_MEAL",
  "items": [
    {"food_id": "chicken_breast", "quantity_g": 200},
    {"food_id": "rice", "quantity_g": 180}
  ]
}
```

Example snack:

```json
{
  "meal_type": "SNACK",
  "slot_role": "SNACK",
  "items": [
    {"food_id": "apple", "quantity_g": 180},
    {"food_id": "verified_protein_bar", "quantity_g": 50}
  ]
}
```

The second example is valid only when both foods are compatible with the user and have verified catalogue data.

The system may display culturally familiar serving equivalents, such as tablespoons or item counts, only when a verified deterministic conversion exists. The canonical quantity used for calculations must remain explicit.

---

## 22. Live food-price provider architecture

Create an explicit provider abstraction equivalent to:

```python
class FoodPriceProvider(Protocol):
    async def get_quotes(...) -> list[FoodPriceQuote]:
        ...
```

Support:

- Multiple providers
- Provider code and name
- Enabled state
- Priority
- Health state
- Provider-specific food mapping
- Fetch timestamp
- Effective date
- Nationwide or regional scope
- Source package size
- Source unit
- Currency
- Raw quote
- Normalized price
- Verification status
- Confidence
- Staleness
- Manual override
- Admin-managed provider
- Import provider
- Development fallback
- Future approved external adapters

Do not couple the planner directly to one retailer.

Implement at least:

1. `DatabaseManagedPriceProvider`
2. `ValidatedImportPriceProvider`
3. `SeedPriceProvider` for development only

Do not use undocumented internal Digikala or Torob APIs.

Do not scrape websites without explicit authorization and a documented legal and technical basis.

### Meaning of live and guaranteed

The application may use wording equivalent to `live price` or `current price` only when the approved live-price policy is satisfied.

When no sufficiently fresh prices are available:

- Do not fabricate a current price.
- Do not silently use seed data.
- Exclude an individual food candidate when only that candidate lacks a required valid fresh price.
- Continue generation only if the remaining priced candidate pool still satisfies configured food-role, nutrition, safety, and price-coverage requirements.
- Return structured `LIVE_PRICE_UNAVAILABLE` with reason `INSUFFICIENT_PRICE_COVERAGE` when missing prices remove required foods/categories or make the remaining candidate pool too incomplete to support a valid budget-aware plan.
- Explain which foods, roles, categories, or providers are missing.
- Allow a clearly labeled stale-data preview only when approved policy and explicit user action permit it.
- Never call stale or seed data today's price.

Price-data absence is not a food preference and must not silently bias the planner into claiming a nutritionally representative optimum from an inadequately covered candidate pool. The versioned price policy must define the minimum coverage conditions needed to proceed.

A stale-data preview may be medically/nutritionally inspected by the physician, but physician review must not convert stale/unavailable pricing into verified current pricing. If the selected product policy requires fresh prices for activation of a budget-aware plan, that activation remains blocked until the price requirement is satisfied.

---

## 23. Price normalization, selection, and provenance

Normalize prices into:

- IRR per gram
- IRR per millilitre
- IRR per item

Use exact integer or `Decimal` arithmetic.

Reject:

- Unsupported currency
- Unknown source quantity
- Invalid quantity
- Negative price
- Unsupported units
- Unmapped products
- Missing effective date for a live quote

Use deterministic selection according to the approved price policy.

Return and snapshot:

- Selected quote
- Source package or source quantity
- Normalized price
- Provider
- Effective date
- Fetch time
- Verification
- Staleness
- Selection reason
- Rejected alternatives and reasons

The user-facing plan must show exact food quantities and calculated cost, not commercial package counts.

---

## 24. Weekly planning model

Create a normalized planning model supporting:

- Weekly plan
- Seven days
- Meals and snacks
- Meal foods
- Exact quantities
- Nutrition totals
- Dietary-quality totals
- Cost totals
- Live-price status
- Price snapshot
- Input snapshot
- Scientific-policy version
- Formula version
- Planner version
- Food-data versions
- Warnings
- Budget status
- Nutrient status
- User explanations
- Revision history
- Regeneration history
- Draft, physician-review, active, and archived states
- Mandatory physician-review state
- Laboratory-information state
- Physician supplement-order state
- Physician approval metadata

Successful plan-revision lifecycle states should include concepts equivalent to:

```text
DRAFT
GENERATED
PENDING_PHYSICIAN_REVIEW
PHYSICIAN_REVIEW_IN_PROGRESS
AWAITING_LAB_INFORMATION
CHANGES_REQUESTED
PHYSICIAN_APPROVED
ACTIVE
ARCHIVED
REJECTED
```

Keep unsuccessful generation outcomes separate from valid plan lifecycle state. A compact generation-result model should support concepts equivalent to:

```text
SUCCESS
FAILED
SAFETY_BLOCKED
INFEASIBLE
TARGET_INFEASIBLE
LIVE_PRICE_UNAVAILABLE
```

Only `SUCCESS` creates a safe feasible plan revision and physician-review request. Other outcomes may persist as auditable generation attempts/results for diagnostics and user explanations, but they must not masquerade as a plan revision that could later become `ACTIVE`.

Rules:

- `GENERATED` is never equivalent to `ACTIVE`.
- Plan lifecycle state and user visibility are separate concerns. A generated plan may be not-active while still being fully visible to its owning user.
- Every otherwise eligible generated Nutrition plan must transition to `PENDING_PHYSICIAN_REVIEW` and remain immediately user-visible.
- `PENDING_PHYSICIAN_REVIEW`, `PHYSICIAN_REVIEW_IN_PROGRESS`, `AWAITING_LAB_INFORMATION`, and `CHANGES_REQUESTED` must never hide an already generated safe draft from its owning user.
- Before real physician approval, the UI must show the current review state and must not show the green physician-approved badge/checkmark.
- Only a real authorized physician action on the exact revision may produce `PHYSICIAN_APPROVED`.
- An approved revision may then become `ACTIVE` according to the approved activation transaction.
- After approval, the UI must show the green physician-approved badge/checkmark, approval date, physician identity according to privacy/product policy, user-visible physician notes, active/prescribed physician supplement orders, and the approved revision.
- If the physician changed plan-defining content, preserve the original generated revision and show the newly approved revision plus a structured user-facing change summary.
- A user meal edit, target change, safety-relevant profile change, or physician plan edit creates or requires a new revision and invalidates approval for the changed revision.
- Laboratory uploads alone do not silently mutate an active plan; they create new medical information for physician review and may trigger reassessment when policy or the physician requires it.
- Do not overwrite historical plans or physician decisions.

## 25. Deterministic budget-aware weekly planner

Implement the planner behind a replaceable interface.

A deterministic heuristic with hard filtering, scoring, validation, and local improvement is acceptable.

Do not add a large optimization dependency unless clearly justified.

OpenRouter must not select or determine:

- Calorie targets
- Nutrient targets
- Ingredient quantities
- Allergy compatibility
- Safety decisions
- Prices
- Budget feasibility
- Medical review requirements
- Supplement recommendations

### Core planner objective

For each user, the planner must solve this practical problem:

1. Determine the scientifically preferred calorie and macronutrient targets.
2. Resolve the applicable versioned micronutrient RDA/AI, UL/CDRR, and medical-policy references.
3. Determine minimum acceptable macronutrient values and applicable nutrient-specific safety limits.
4. Load verified foods compatible with the user's medical and dietary constraints and their deterministic nutrition slot-role metadata.
5. Load normalized fresh prices according to policy.
6. Estimate which combination of foods can satisfy calorie, macronutrient, core micronutrient, and diet-quality objectives within the weekly budget.
7. If all preferred targets cannot be fully met, find the closest safe feasible plan without pretending that every reference was achieved.
8. Show the exact gap between preferred/planned macronutrients and the dietary-reference gap for supported micronutrients.
9. Create exactly the effective number of user-selected main-meal and snack slots.
10. Distribute daily calorie and macronutrient targets across those slots under versioned meal-distribution policy.
11. Build each slot using exact verified food quantities appropriate for its role.
12. Improve micronutrient adequacy during candidate scoring rather than waiting until after a macro-only plan is finalized.
13. Run a bounded deterministic micronutrient repair pass for remaining important gaps.
14. Show nutrient contribution and cost at item, meal, day, and week levels.

The planner should be able to compare alternative protein-source mixes such as chicken, meat, eggs, dairy, legumes, soy, and other verified compatible foods.

It should also allocate carbohydrate and fat sources to satisfy the full nutritional plan rather than optimizing protein in isolation.

The cheapest plan is not automatically the best plan.

### Hard constraints

Include:

- Age eligibility
- Safety decision
- Medical-condition policy
- Allergies
- Intolerances
- Explicit medical or dietary exclusions
- Dietary pattern when applicable
- Cultural restrictions when applicable
- User-selected main-meal count bucket and effective slot count
- User-selected snack count bucket and effective slot count
- Main-meal versus snack food-role eligibility
- Valid mandatory nutrient data
- Valid live normalized price for each selected food in strict-live mode, plus configured minimum price-coverage requirements for the candidate pool
- `STRICT` budget ceiling when strict mode is selected
- Nutritional safety floors, including fibre only when an approved safety/medical policy explicitly classifies fibre as hard for that user
- Applicable nutrient-specific UL or medical maximum where the authoritative policy defines one
- Medical-condition micronutrient restrictions

### Soft constraints

Include:

- Preferred calories
- Preferred protein
- Meal-distribution quality under the approved policy
- Carbohydrate range
- Fat range
- Fibre adequacy by default; it becomes hard only through an explicit approved safety/medical policy
- Free-sugar control
- Saturated-fat control
- Trans-fat control
- Sodium AI/CDRR behavior under policy
- Calcium adequacy
- Potassium adequacy
- Magnesium adequacy
- Iron adequacy
- Zinc adequacy
- Vitamin C adequacy
- Vitamin D dietary adequacy
- Vitamin B12 adequacy
- Folate adequacy
- Additional configured micronutrient adequacy metrics when reliable
- Foods the user likes
- Foods the user dislikes
- Variety
- Repetition limit
- Ingredient reuse when useful for budget efficiency
- `FLEXIBLE` budget target, configured overage penalty/cap, and general cost efficiency
- Day context
- Availability in Iran
- Prior meal feedback
- Prior adherence difficulties

### Micronutrient-aware optimization and repair

Do not use a naive loop of `generate whole plan -> reject for one micronutrient -> regenerate whole plan from scratch`.

The preferred strategy is:

```text
constraint-aware candidate generation
-> multi-nutrient scoring
-> select best feasible plan
-> targeted local micronutrient repair
-> full revalidation
```

Micronutrients must influence candidate scoring from the start. The final repair pass is for remaining gaps, not the first time the planner considers micronutrients.

For each repair iteration:

1. Rank important unresolved micronutrient gaps using versioned policy.
2. Identify compatible foods that efficiently contribute to the gap while respecting allergies, medical restrictions, meal role, likes/dislikes, price availability, and budget.
3. Prefer a small substitution or portion change over rebuilding the entire plan.
4. If a nutrient-dense food adds calories or macros, rebalance another compatible food so calorie and macronutrient targets remain within tolerance.
5. Recalculate **all** nutrients and cost after every accepted repair.
6. Reject repairs that create a new hard safety violation or a worse overall objective score.
7. Use deterministic tie-breakers and a bounded maximum number of iterations.
8. Keep the best validated feasible state seen so far to prevent oscillation.

Example concept:

```text
Zinc below reference
-> identify zinc-dense compatible candidates
-> increase or substitute one candidate
-> reduce an energy-equivalent food if needed
-> recheck calories, protein, fat, carbohydrate, zinc, iron, sodium, other micronutrients, and budget
```

A micronutrient repair must not blindly maximize the nutrient. The goal is adequate intake within the applicable reference policy, not `more is always better`.

If a reference target cannot be reached because of budget, food availability, data incompleteness, preferences, or medical restrictions, preserve the safest best-feasible plan and report the unresolved gap unless the policy classifies that gap as a hard safety failure.

---

## 26. Planner scoring, tolerances, and validation

Compare normalized deviations rather than raw units.

Support metrics equivalent to:

```text
calorie_deviation_ratio
protein_deficit_ratio
carbohydrate_deviation_ratio
fat_deviation_ratio
fiber_deficit_ratio
free_sugar_excess_ratio
saturated_fat_excess_ratio
trans_fat_excess_ratio
sodium_policy_deviation_ratio
micronutrient_deficit_ratio[nutrient_code]
micronutrient_upper_limit_excess_ratio[nutrient_code]
micronutrient_data_incompleteness_penalty
micronutrient_repair_change_penalty
budget_excess_ratio
repetition_penalty
preference_penalty
adherence_risk_penalty
```

Store scoring weights and allowed tolerances in versioned policy.

Do not place unexplained magic weights in planner functions.

Validate at:

- Meal level where relevant
- Day level
- Week level

The planner must distinguish a warning from an infeasible plan according to approved policy.

A single micronutrient below RDA or AI must not automatically make a plan `INFEASIBLE`. The policy must define which micronutrient conditions are soft adequacy gaps, which are hard medical constraints, and which upper-limit violations block activation.

For each supported micronutrient, policy must explicitly define its aggregation window and, only when scientifically justified, an optional daily guard/floor. If no daily guard is defined for that nutrient, weekly/rolling adequacy must not be converted into an invented daily hard threshold.

Planner scoring must avoid double-counting correlated objectives. Keep calorie/macronutrient adequacy, micronutrient adequacy, diet quality, preference, repetition, and cost weights explicitly versioned and reviewable.

---

## 27. Planner sequence

The planner should:

1. Validate the unified profile.
2. Check age eligibility.
3. Run current safety screening.
4. Determine whether automatic draft generation is allowed, physician-manual planning is required, or the case is unsupported.
5. Calculate BMR and TDEE.
6. Calculate calorie, macronutrient, fibre, sugar, fat-quality, and sodium-policy targets.
7. Resolve applicable micronutrient RDA/AI, UL/CDRR, modifiers, and medical overrides from versioned policy.
8. Resolve the selected main-meal and snack buckets into effective plan slot counts.
9. Create required `MAIN_MEAL` and `SNACK` slots.
10. Convert monthly budget into weekly budget.
11. Load and validate live-price availability.
12. Filter unsafe and incompatible foods.
13. Filter foods lacking mandatory safety/macro data and mark micronutrient data completeness separately.
14. Classify candidate foods/compositions by `MAIN_MEAL` versus `SNACK` eligibility.
15. Generate candidate main-meal protein-source combinations.
16. Generate candidate carbohydrate-source combinations for main meals.
17. Generate candidate fat and complementary-food combinations.
18. Generate snack candidates from verified snack-eligible foods.
19. Allocate daily calorie and macronutrient targets across the selected slot structure under versioned policy.
20. Build complete main-meal and snack combinations.
21. Optimize exact portions across all slots using calorie, macronutrient, micronutrient, diet-quality, preference, and budget scoring.
22. Validate calories and macronutrients.
23. Validate fibre and diet-quality limits.
24. Validate micronutrient adequacy, applicable UL/CDRR semantics, and data completeness.
25. Validate meal-role rules.
26. Validate cost.
27. Attempt economical substitutions when needed without violating slot role or safety.
28. Attempt better protein combinations when needed.
29. Run bounded targeted micronutrient repair for remaining important gaps.
30. Revalidate the entire plan after repair, including macros, all supported micronutrients, safety, meal roles, and budget.
31. Improve variety and controlled repetition only when it does not materially worsen higher-priority objectives.
32. Generate deterministic explanations from structured reason codes.
33. Generate the exact-quantity shopping list.
34. Persist an immutable snapshot including meal-structure inputs, micronutrient reference rows, repair actions, and policy versions.
35. Persist the safe generated draft, then hand it to the separate physician-review lifecycle; physician approval is not part of food-ranking/scoring.

Avoid creating 21 completely unrelated meals.

Use controlled repetition when it improves affordability, adherence, or simplicity of the nutrition plan.

---

## 28. Structured nutrition status and ideal-versus-achievable reporting

For every important metric return:

- Estimated requirement or selected dietary-reference value
- Reference kind when applicable (`RDA`, `AI`, `UL`, `CDRR`, medical override)
- Preferred target
- Minimum or maximum limit
- Planned amount
- Difference from preferred
- Difference from minimum or maximum where relevant
- Status
- Reason codes
- Data confidence

Support statuses equivalent to:

```text
WITHIN_TARGET
BELOW_MINIMUM
BELOW_PREFERRED_BUT_ACCEPTABLE
ABOVE_LIMIT
DATA_INCOMPLETE
BELOW_REFERENCE_TARGET
ABOVE_APPLICABLE_LIMIT
```

Example:

```json
{
  "metric": "protein",
  "preferred_target_g": 145,
  "minimum_acceptable_g": 110,
  "planned_g": 132,
  "status": "BELOW_PREFERRED_BUT_ACCEPTABLE",
  "difference_from_preferred_g": -13,
  "reasons": [
    "budget_constraint",
    "economical_protein_mix_selected"
  ]
}
```

Do not claim a target was reached when it was not.

### Required summary

Every generated plan must have a user-readable summary conceptually equivalent to:

```text
Preferred daily target
- Calories: ...
- Protein: ...
- Carbohydrates: ...
- Fat: ...
- Fibre: ...

Planned daily average with current budget
- Calories: ...
- Protein: ...
- Carbohydrates: ...
- Fat: ...
- Fibre: ...

Gap from preferred
- Calories: ...
- Protein: ...
- Carbohydrates: ...
- Fat: ...
- Fibre: ...

Estimated weekly cost: ... IRR
Weekly budget: ... IRR
```

---

## 29. Insufficient budget

Never shame the user.

Distinguish:

1. Nutritional safety floor
2. Preferred fitness target
3. Achievable amount under the budget

When the preferred plan does not fit:

- Use economical compatible foods.
- Consider legumes, eggs, dairy, soy, poultry, fish, and red meat according to verified data, medical compatibility, preference, and cost.
- Reduce unnecessary variety when appropriate.
- Reuse compatible ingredients when it reduces cost.
- Explain the compromise.
- Show the planned nutrient amount and its gap from the preferred target.
- Show unresolved core micronutrient reference gaps when reliable data supports the calculation.
- Prefer economical substitutions that improve more than one nutrient objective when possible.

A Persian explanation may communicate:

> با بودجه فعلی رسیدن کامل به هدف ترجیحی پروتئین دشوار است. برنامه فعلی با استفاده از منابع اقتصادی‌تر، نزدیک‌ترین ترکیب قابل‌دستیابی را فراهم کرده است.

When the budget cannot satisfy safety floors:

- Return `INFEASIBLE`.
- Do not activate an inadequate plan.
- Return current budget.
- Return estimated minimum budget when it can be calculated reliably.
- Return estimated gap.
- Return limiting constraints.
- Return safe suggested changes.

---

## 30. Exact-quantity shopping list

Generate a weekly shopping list that:

- Merges duplicate foods
- Keeps exact required quantities
- Uses the same canonical quantity semantics as the nutrition plan
- Shows the exact amount used by the plan
- Shows nutritional contribution, including protein contribution where relevant
- Shows item cost
- Shows total cost
- Shows provider and effective date
- Shows live, stale, estimated, or unavailable status
- Avoids floating-point errors

Do not tell the user to buy one, two, or another number of commercial packages.

Do not convert exact required quantities into package recommendations.

Example display:

```text
سینه مرغ: ۲.۳ کیلوگرم
پروتئین تأمین‌شده در برنامه: ... گرم
هزینه تخمینی این مقدار: ... ریال
منبع قیمت: ...
تاریخ قیمت: ...
```

Shopping-list nutritional and cost totals must match plan totals.

When the shopping list belongs to a revision that is still awaiting physician approval, it remains visible but must carry a clear user-facing warning equivalent to: `این برنامه هنوز در انتظار تأیید پزشک است و ممکن است تغییر کند؛ خرید نهایی را بعد از تأیید انجام دهید.` The warning disappears for the active approved revision.

---

## 31. Meal editing, locking, and partial regeneration

Allow the user to:

- Remove a planned meal
- Replace a planned meal
- Replace a food item
- Lock or unlock a meal
- Regenerate unlocked meals
- Request a cheaper option
- Request more protein
- Request more variety

Keep **actual-consumption changes** separate from **plan-defining changes**.

- `CONSUMPTION_ONLY`: the user reports what they actually ate, skipped, replaced, or portion-adjusted on a specific day. This belongs to tracking and does **not** modify the approved plan revision or invalidate physician approval.
- `PLAN_CONTROL_METADATA`: actions such as locking/unlocking a meal or leaving feedback without changing foods/quantities do not by themselves invalidate the approved revision.
- `PLAN_DEFINING`: changing planned foods, planned quantities, calorie/macro targets, meal-slot structure, or regenerating content creates a new immutable revision and requires deterministic revalidation and physician re-review.

Do not create a generic `±X grams` bypass for physician review. Classification depends on whether the **plan definition** changed, not on an arbitrary magnitude threshold.

Before a plan-defining change, show:

- Calorie difference
- Protein difference
- Carbohydrate difference
- Total-fat difference
- Fibre difference
- Free-sugar difference where known
- Saturated-fat difference
- Sodium difference
- Cost difference
- Daily effect
- Weekly effect
- New warnings
- Review-approval consequences

Do not modify the plan until confirmation.

### Concurrent review protection

When the current physician review is `IN_REVIEW`, temporarily block user-initiated `PLAN_DEFINING` edits and regeneration for that review lineage. The user may still log actual intake, weight, adherence, notes, and other `CONSUMPTION_ONLY` or non-plan metadata.

Every plan-defining mutation and every physician approve/edit action must carry the expected current `plan_revision_id` (or equivalent optimistic-concurrency token). Reject stale mutations with a structured conflict if the revision changed before commit; never approve or overwrite a stale revision.

After confirmation of a plan-defining change when editing is allowed:

- Create a new immutable revision.
- Recalculate totals.
- Recalculate the shopping list.
- Preserve history.
- Invalidate approval only for the changed/new revision.
- Create or refresh the physician-review request for that revision.
- Maintain at most one **current nonterminal Nutrition review lineage** per user. If a new user-generated revision replaces a pending/changes-requested revision, archive/supersede the previous draft in history and mark its review `INVALIDATED_BY_REVISION`. Do not run parallel competing reviews for the same current Nutrition plan.

Locked meals must still be validated against current allergies, safety rules, food data, price policy, budget, and plan-wide totals.

---

## 32. Meal feedback and future scoring

Allow feedback:

```text
LIKED
DISLIKED
DO_NOT_SUGGEST_AGAIN
PREFER_MORE_OFTEN
TOO_LARGE
TOO_SMALL
```

Use feedback in future scoring.

Feedback must not modify nutrient values or override safety.

`DO_NOT_SUGGEST_AGAIN` is a post-plan feedback action, not an additional onboarding preference question.

Allow a previous suitable plan to be the starting point for a new week, but recalculate it using current body data, goal, policies, food data, prices, preferences, and adherence information.

Do not reactivate an old snapshot without recalculation.

---

## 33. Low-friction daily calorie and food-consumption tracking

Implement real daily calorie tracking without requiring the user to manually enter every food every day.

The system must support both quick approximate tracking and optional detailed tracking.

### Tracking baseline rule

A visible `PENDING_PHYSICIAN_REVIEW` draft is **not** an adherence baseline. The user may still manually log actual foods, use photo logging, or record off-plan intake while waiting for physician review.

`ON_PLAN` and `MOSTLY_ON_PLAN` may prefill intake only from the physician-approved `ACTIVE` plan revision that is effective for that date. Any consumption entry derived from a plan must store the exact `plan_revision_id` used as its baseline.

If the physician later approves a different revision, historical consumption/adherence records remain pinned to the revision that was actually active for those dates; do not retroactively recalculate the past against a newer revision unless an explicit audited correction workflow is used.

### Daily quick check-in

Provide one low-friction daily check-in with choices equivalent to:

```text
ON_PLAN
MOSTLY_ON_PLAN
OFF_PLAN
NOT_RECORDED
```

Persian UI examples:

- `طبق برنامه بودم`
- `تقریباً طبق برنامه بودم`
- `امروز برنامه را رعایت نکردم`

Do not create consumption records merely because a plan exists. User action is required.

#### ON_PLAN

With one confirmation:

- Prefill actual intake approximately from planned meals.
- Allow optional portion corrections.
- Mark entries as estimated from the plan, not directly measured.

#### MOSTLY_ON_PLAN

- Prefill the planned day.
- Ask only about deviations.
- Allow the user to mark skipped meals, changed portions, replacements, or extras.
- Do not require re-entering meals that were followed.

#### OFF_PLAN

Do not ask the user to record every bite.

Offer simple approximate methods:

- Photograph one or more main meals
- Select a food or meal from the catalogue
- Use recent foods
- Use a quick approximate meal category and portion
- Enter only major foods or deviations

Clearly label the result as approximate.

### Optional detailed tracking

Users who want more precision may:

- Mark a planned meal as eaten
- Mark it as skipped
- Change the actual portion
- Record part of a meal
- Add a food outside the plan
- Add a structured custom meal from catalogue foods
- Edit or delete their own entries
- Add a note that does not affect calculations

Free text alone must not create numeric nutrient totals.

### Log sources and confidence

Every consumption entry must record a source equivalent to:

```text
PLANNED_CONFIRMED
PLANNED_ADJUSTED
CATALOGUE_MANUAL
PHOTO_ESTIMATED_CONFIRMED
PHOTO_ESTIMATED_EDITED
QUICK_APPROXIMATION
PROFESSIONAL_ENTRY
```

Also store confidence and whether the user confirmed the value.

If a day has insufficient information, return `INSUFFICIENT_DATA` rather than a misleading adherence score of zero.

---

## 34. Photo-assisted food and calorie estimation using OpenRouter

Cooking is explicitly outside this Nutrition Core specification. Nutrition decides what foods and exact quantities belong in the plan; a separate future Cooking specification may decide how those foods are prepared.

OpenRouter is allowed only for photo-based food estimation inside the calorie counter.

Do not use OpenRouter for any other Nutrition feature.

### Required user flow

1. The user uploads or captures a food photo.
2. The backend validates file type, size, ownership, and safety.
3. The configured OpenRouter vision model receives the image and a strict structured prompt.
4. The model returns candidate foods, estimated portions, uncertainty, and visible limitations.
5. The deterministic food catalogue maps candidates to verified food records.
6. Calories and nutrients are calculated from verified catalogue data, not accepted directly from the model when a verified mapping exists.
7. The user sees the estimate and confidence.
8. The user must confirm, edit, remove, or replace detected items. If a confirmed item conflicts with an allergy/hard exclusion, allow truthful actual-intake logging with a prominent safety warning; do not make that item planner-eligible.
9. Only the confirmed or edited result is written to calorie history.

Never automatically write an unconfirmed AI result into consumption history.

Never describe a photo estimate as exact.

### Structured model output

Require a validated schema containing concepts equivalent to:

```json
{
  "meal_name_guess": "string or null",
  "items": [
    {
      "name_guess": "string",
      "estimated_amount": 0,
      "unit": "g|ml|item|unknown",
      "confidence": 0.0,
      "visible_evidence": ["string"],
      "uncertainties": ["string"]
    }
  ],
  "overall_confidence": 0.0,
  "needs_user_confirmation": true
}
```

Reject malformed output.

Do not allow the model to invent authoritative calories, nutrition facts, allergies, or medical suitability.

When an item cannot be mapped reliably:

- Show it as unresolved.
- Ask the user to choose a catalogue item or enter an approximate structured alternative.
- Do not silently map it to an unrelated food.

### OpenRouter integration

Use OpenRouter's official multimodal image-input API through its supported flow or the repository's established compatible client.

Model discovery must use official model metadata and validate that the selected model supports image input.

Support:

- Primary vision model
- Ordered fallback vision models
- Timeout
- Retry policy
- Maximum image size
- Maximum images per request
- Maximum response tokens
- Low deterministic temperature where supported
- Structured output mode where supported
- Provider-routing policy
- Optional Zero Data Retention routing where supported and enabled
- Per-request cost and token accounting
- Connection test
- Feature enable/disable

Do not hardcode one model ID in business logic.

### Privacy and retention

Before sending a food photo to OpenRouter:

- Show clear user consent describing third-party processing.
- Do not send name, email, birth date, detailed medical history, or unrelated profile data.
- Send only the minimum context required for food identification.
- Remove image metadata where practical.
- Use temporary storage with a documented retention policy.
- Allow the user to delete uploaded photos and derived estimates.
- Do not use photos for model training or unrelated analytics without separate consent.

If OpenRouter is disabled or unavailable, manual and catalogue-based calorie tracking must continue to work.

---

## 35. Admin AI settings for food-photo estimation

Extend the existing admin AI-model settings area rather than building an unrelated settings system.

Add a distinct feature configuration equivalent to:

```text
FOOD_PHOTO_ESTIMATION
```

The admin interface must support:

- Provider fixed to `OPENROUTER` for this feature
- Encrypted API key storage
- Masked API-key display
- API-key replacement and deletion
- Feature enable/disable
- Primary vision-model selection
- Fallback-model ordering
- Model capability validation
- Model refresh from OpenRouter's official model list
- Timeout
- Retry count
- Maximum image bytes
- Maximum image count
- Maximum response tokens
- Temperature where supported
- Structured-output enablement where supported
- Provider-routing options
- Privacy options, including ZDR preference where supported
- Daily or monthly usage limit
- Per-request cost limit where feasible
- Test connection
- Test image request with no production logging
- Last successful request
- Last error
- Usage and estimated cost metrics
- Audit history for settings changes

Never return the plaintext API key after storage.

Only authorized admins may view or modify these settings.

Photo estimation must fail closed when no valid model or key is configured.

---

## 36. Planned versus actual daily summary

For every tracked day, calculate and display:

- Planned calories
- Actual or approximately actual calories
- Calorie difference
- Planned protein and actual protein
- Planned carbohydrates and actual carbohydrates
- Planned fat and actual fat
- Planned fibre and actual fibre where data is sufficient
- Meal adherence
- Logging completeness
- Entry confidence
- Structured-exercise calories separately

Do not add exercise calories twice.

Do not automatically grant extra food calories merely because an exercise session was logged unless approved policy explicitly does so.

Show estimated and exact values differently.

A photo or quick-check-in estimate must remain labeled as approximate in summaries and history.

---

## 37. Adherence metrics, charts, and history

Do not reduce adherence to one opaque score.

Calculate visible components such as:

- Calorie-target adherence
- Protein-target adherence
- Planned-meal adherence
- Budget adherence where actual food costs are available
- Number of major deviations
- Tracking completeness
- Estimate confidence

A composite adherence score may be provided only when:

- Its formula is versioned.
- Its components are visible.
- Insufficient data does not become a false low score.
- It is not used to shame the user.

### Charts

Provide mobile-friendly charts for:

- Planned versus actual daily calories
- Daily protein planned versus actual
- Daily adherence components
- Weekly calorie and macro averages
- Weight trend beside adherence, without claiming simple causation
- Tracking completeness
- Exact versus approximate entry proportion

Provide history filters by:

- Date range
- Week
- Entry source
- On-plan, mostly-on-plan, or off-plan day
- Exact or approximate data

### UX principles

- One daily check-in is enough for ordinary users.
- Do not require every snack or drink to be logged.
- Use reminders only when enabled.
- Do not create punitive streaks.
- Make detailed tracking optional.
- Allow backfilling a recent day approximately.
- Explain that lower-effort tracking has lower precision.

---

## 38. Adaptive planning for the next week

Use actual or approximate adherence data to improve practical plan fit.

The system may adapt:

- Disliked meals
- Meals repeatedly skipped
- Portions repeatedly reduced or increased
- Repetition tolerance inferred from feedback
- Meal timing
- Work-day context
- Ingredient availability
- Preferred level of logging effort

The system must not automatically change scientific calorie or nutrient targets merely because the user under-ate or over-ate.

Changes to calorie targets must require:

- Sufficient weight and adherence history
- Approved scientific policy
- Minimum data-quality threshold
- Clear explanation
- User confirmation
- Physician approval for every new or materially revised Nutrition plan

Store the reason for every adaptive change.

---

## 39. Laboratory records and mandatory physician review workflow

Every generated Nutrition plan for every supported user must be reviewed by an authorized Fitsho physician before activation.

This requirement applies to users with and without known medical conditions. Medical-condition policy still determines whether an automatic draft is allowed, whether manual physician planning is required, or whether the case is unsupported.

### 39.1 Laboratory-record upload

Provide a secure user-facing area equivalent to `آزمایش‌های من`.

The user must be able to upload laboratory documents such as:

- PDF
- JPG/JPEG
- PNG

Store a normalized laboratory-document record with at least:

- Owner user ID
- Original secure file reference
- File type
- Upload timestamp
- User-declared laboratory/test date when known
- Optional laboratory/provider name
- Optional user note
- Optional document category
- Laboratory document review status
- Related physician laboratory-request ID when applicable
- Assigned physician when applicable
- Created and updated timestamps

Do not require laboratory uploads from every ordinary user. A physician must be able to approve an otherwise appropriate plan without laboratory testing when clinical judgment does not require tests.

A physician must also be able to request additional or repeat laboratory information. A request should support:

- Requested test or information description
- Clinical reason visible to the user where appropriate
- Request date
- Optional requested-by date
- Status such as `REQUESTED`, `UPLOADED`, `REVIEWED`, `CANCELLED`

If required information is missing, the physician may move the plan review into `AWAITING_LAB_INFORMATION`; the plan remains not activated but the already generated draft remains fully visible to the owning user with a clear laboratory-request status.

### 39.2 Laboratory interpretation boundary

For this implementation, the original laboratory image/PDF is the authoritative user-supplied record reviewed by the physician.

Do not use OpenRouter or another LLM to diagnose laboratory abnormalities or prescribe supplements.

Future OCR or structured extraction may be added only as an assistive data-entry feature. If extraction is later introduced:

- Preserve the original document.
- Mark extracted values as machine-extracted until physician-confirmed.
- Store value, unit, reference range, source page, confidence, and confirmation state separately.
- Never convert an unconfirmed extraction into a diagnosis or supplement order.

### 39.3 Mandatory plan submission

After the deterministic planner returns a `SUCCESS` generation outcome and completes all safety, budget, macronutrient, micronutrient, meal-role, and price validation:

1. Persist an immutable draft revision.
2. Make that complete draft immediately visible to the owning user.
3. Create a physician-review request automatically.
4. Attach the exact plan revision, profile snapshot, medical/safety snapshot, nutrient analysis, micronutrient adequacy summary, unresolved dietary gaps, price snapshot, and available laboratory-document references.
5. Set the plan to `PENDING_PHYSICIAN_REVIEW`.
6. Show a clear pending-review label/banner to the user and do not show any physician-approved green badge/checkmark.
7. Do not activate the plan until an authorized physician approves the exact revision.
8. Keep the user-visible draft accessible while review is pending, in progress, waiting for laboratory information, or awaiting requested changes.

### 39.3A Plan/review state synchronization

Plan state and review-request state are separate entities but must follow an explicit mapping so API and UI cannot drift:

| Event | Plan state | Review state |
| --- | --- | --- |
| Safe draft submitted | `PENDING_PHYSICIAN_REVIEW` | `PENDING` |
| Physician opens review | `PHYSICIAN_REVIEW_IN_PROGRESS` | `IN_REVIEW` |
| Physician requests labs | `AWAITING_LAB_INFORMATION` | `AWAITING_LAB_INFORMATION` |
| Physician requests plan changes | `CHANGES_REQUESTED` | `CHANGES_REQUESTED` |
| Exact revision approved | `PHYSICIAN_APPROVED`; activation follows the explicit effective-date rule in §39.5 | `APPROVED` |
| Review rejected | `REJECTED` | `REJECTED` |
| Reviewed revision replaced by a new plan-defining revision | new revision returns to `PENDING_PHYSICIAN_REVIEW` unless it is created inside the same authorized physician review session | old review becomes `INVALIDATED_BY_REVISION` or is explicitly rebound according to the rule below |

`GENERATED` may be a short-lived internal state between planner persistence and review-request creation; it must not remain an ambiguous long-lived user-facing state when a review request exists.

When a physician edits the plan during an authorized review, create revision `N+1`, rerun full deterministic validation, and bind the current review session to `N+1`. If validation passes, the same authorized physician may approve `N+1` in the same review session; do not force the physician to the back of the queue merely because their own structured edit created a new revision.

If the physician sets `CHANGES_REQUESTED`, include a user-visible structured reason/action request. The next plan-defining revision may be created by the user/regeneration flow or by the physician through the authorized structured editor. A new user-created revision invalidates the old review and starts a new pending review; a physician-created revision may use the same-session rebind rule above. Do not leave `CHANGES_REQUESTED` without an explicit next-action path.

If the review is already `IN_REVIEW`, user plan-defining edits/regeneration are blocked as defined in Section 31. This prevents a physician from approving a revision that the user changed concurrently.

Physician queues should minimally track assignment, priority, `created_at`, `review_started_at`, optional `target_review_by`, reassignment, and overdue state. These fields support operations only; they must never create auto-approval or bypass the physician requirement.

### 39.4 Physician review actions

The physician must be able to:

- View the user's relevant declared conditions, medications, allergies, intolerances, and dietary restrictions
- View available laboratory documents in a secure viewer
- Request additional or repeat laboratory information
- View BMR/TDEE methodology, calorie target, macro targets, micronutrient reference rows, and confidence
- View every main meal, snack, food, exact quantity, nutrient total, micronutrient contribution, and cost
- View unresolved dietary-reference gaps and every accepted micronutrient-repair action
- View budget constraints and price provenance
- Approve the exact plan revision
- Reject the revision
- Request changes
- Edit foods and quantities through structured controls
- Edit medically relevant constraints or add a professional note through authorized workflows
- Create a new revision after an edit
- Rerun deterministic validation after every structured edit
- Create, modify, discontinue, or complete physician supplement orders
- Link supplement decisions to laboratory documents or another documented clinical rationale when appropriate
- Add user-visible and internal professional notes
- Record reasons for clinically meaningful actions

### 39.5 Approval and activation

Approval applies only to the exact reviewed revision.

A physician edit must not bypass hard allergy validation, medical-policy rules, a user-selected `STRICT` budget ceiling, or database integrity. There is no hidden `CLINICAL_BUDGET_OVERRIDE`: if a medically preferred change cannot fit a strict budget, the physician may explain/request a budget-mode or budget change, but the system must not silently spend beyond the user's strict ceiling.

Any later user or professional change to meals, quantities, foods, calorie/macro targets, safety-relevant restrictions, or another plan-defining input invalidates approval for the changed revision and requires a new physician review before that revision becomes active.

#### Activation transaction

Activation is a deterministic system transaction after physician approval; it is not a second clinical approval. Persist an `effective_start_date` in the approved revision snapshot. Use the user-selected/precomputed future plan start date when one exists; otherwise default `effective_start_date` to the physician-approval date.

- If `effective_start_date` is today or in the past at the time approval commits, activate the approved revision immediately.
- If `effective_start_date` is in the future, keep the revision `PHYSICIAN_APPROVED` and activate it when that date becomes effective.
- For a user and overlapping effective date range, only one Nutrition revision may be the current `ACTIVE` adherence baseline. Activating a replacement revision must atomically supersede/archive the previously active revision for overlapping future dates while preserving history.
- Tracking for each date remains pinned to the revision that was actually active for that date.
- Activation must recheck revision identity, approval validity, hard safety invariants, and any activation-time requirement explicitly defined by policy; it must not rerun physician judgment or silently mutate plan contents.

Do not display wording implying physician review before a real physician has reviewed the exact revision.

Only after approval may the UI display wording equivalent to:

> این نسخه از برنامه غذایی توسط پزشک فیتشو بررسی و تأیید شده است.

After approval, the user-facing plan experience must also:

- Replace the pending-review presentation with a green physician-approved badge/checkmark.
- Show approval date and physician identity according to privacy/product policy.
- Display the exact approved revision rather than silently mutating the pre-review draft.
- If the physician changed foods, quantities, targets, restrictions, or other plan-defining content, show a structured `PhysicianChangesSummary` describing what changed between the original generated revision and the approved revision.
- Show all physician notes explicitly marked user-visible. Internal physician notes must never be exposed to the user.
- Show physician-created supplement orders associated with the user's care, including dose, frequency, duration/date, instructions, and status.
- Notify the user that physician review is complete and indicate whether the physician approved without changes, approved with changes, requested laboratory information, or requested another revision.
- Preserve access to prior revisions in plan history so the user can understand that a physician-created revision replaced or modified the original generated draft.

### 39.6 Review states

Support states equivalent to:

```text
PENDING
IN_REVIEW
AWAITING_LAB_INFORMATION
CHANGES_REQUESTED
APPROVED
REJECTED
INVALIDATED_BY_REVISION
```

There is no ordinary `NOT_REQUIRED` state for a generated Nutrition plan in this product design. Every otherwise supported plan requires physician approval before activation.

## 40. Physician panel

Build a dedicated protected physician panel. A coach panel is not part of this Nutrition specification.

### 40.1 Review queue

Include:

- Assigned review queue
- Unassigned review queue where permitted
- Queue filters by status, date, plan goal, laboratory-information state, and urgency where policy supports it
- Clear distinction between new plan review, changed revision review, laboratory follow-up, and supplement follow-up

### 40.2 User medical and nutrition workspace

For each authorized user, show a coordinated workspace containing:

- Identity fields necessary for care
- Age, sex, height, current weight, and relevant body-composition data
- Primary goal
- Activity and structured-exercise summary
- Medical conditions
- Current medications
- Allergies and intolerances
- Dietary restrictions
- Relevant symptoms or safety answers supported by policy
- Weight/adherence history where relevant
- Current and historical Nutrition plan revisions
- Current physician approval state

### 40.3 Laboratory workspace

Include:

- Secure original PDF/image viewer
- Laboratory-document metadata
- Review state
- Physician notes
- Ability to mark a document reviewed
- Ability to request additional/repeat tests
- Ability to link a document to a supplement order or clinical note
- Audit trail of access and review actions

Do not expose one user's laboratory records to another user or unauthorized reviewer.

### 40.4 Nutrition-plan review workspace

Include:

- Exact plan-revision viewer
- Main-meal and snack structure
- Exact food quantities
- Calories and macronutrients
- Fibre and diet-quality metrics
- Core micronutrient targets, reference kinds, planned intake, gap, confidence, and upper-bound semantics
- Micronutrient repair history
- Budget and exact cost
- Price provenance
- Deterministic safety validation
- Structured plan editor
- Approve, reject, request-changes, and request-lab-information actions
- User-visible and internal notes
- Review history

### 40.5 Supplement workspace

Include:

- Current and historical physician supplement orders
- Dietary micronutrient gap summary
- Relevant laboratory documents
- Current medications and contraindication context
- Supplement catalogue search
- Structured supplement-order editor
- Start, modify, discontinue, complete, and follow-up actions
- Audit trail

### 40.6 Authorization

Use explicit roles and permissions.

At minimum:

```text
ADMIN
PHYSICIAN
USER
```

Design the role model so another qualified professional role can be added later without redesigning core ownership tables.

Physicians must only access users and records they are assigned or otherwise explicitly authorized to review.

## 41. Physician-managed supplement system

Implement a real physician-managed supplement workflow integrated with Nutrition, micronutrient analysis, and laboratory records.

This scope includes supported vitamins, minerals, nutritional supplements, protein products, creatine, and other supported supplement-like products. Prescription medications remain outside the supplement catalogue and must not be altered by this workflow.

### 41.1 Core principle

Fitsho's deterministic Nutrition planner must remain food-first.

The planner must:

1. Calculate the user's dietary reference targets.
2. Optimize the food plan with micronutrients included in candidate scoring.
3. Run the bounded targeted food-repair pass.
4. Preserve primary calorie, macronutrient, safety, meal-role, and budget constraints.
5. Report any important unresolved dietary micronutrient gaps to the physician.

The planner must **not** automatically prescribe or activate a supplement because a dietary reference target is low.

A low dietary intake is not equivalent to a laboratory-confirmed deficiency.

### 41.2 Physician supplement order

Only an authorized physician may create the final active supplement order in this Nutrition workflow.

A structured `PhysicianSupplementOrder` should support at least:

- User ID
- Physician ID
- Supplement catalogue item or documented generic supplement ingredient
- Nutrient/active ingredient
- Dose amount
- Dose unit
- Frequency
- Optional route when relevant
- Start date
- Optional end date or duration
- User-facing instructions
- Clinical rationale
- Optional linked micronutrient dietary gap
- Optional linked laboratory document(s)
- Optional follow-up laboratory request
- Contraindication/interactions check result
- Status
- Created, modified, discontinued, and completed timestamps
- Audit metadata

Statuses should include concepts equivalent to:

```text
DRAFT
PRESCRIBED
ACTIVE
COMPLETED
DISCONTINUED
CANCELLED
```

### 41.3 Safety

Before an order is activated:

- Run deterministic known-allergen and configured contraindication checks.
- Surface current medications and relevant conditions to the physician.
- Calculate proposed combined exposure from the applicable approved food-plan revision plus the proposed supplement order when both contributions are known.
- Evaluate configured nutrient upper-bound semantics where applicable.
- Block activation with a structured safety result when the proposed combined exposure violates a hard nutrient/medical upper limit; physician acknowledgement must not override a configured hard block.
- Never infer that exceeding or approaching a dietary reference value is safe merely because the source is a supplement.
- Require the physician to resolve or explicitly acknowledge supported non-blocking warnings according to policy.

If safe supplement use requires a plan-defining food change, create a new plan revision and run the normal validation/review workflow rather than silently reducing food quality.

Fitsho must not automatically modify prescription medications.

### 41.4 Food versus supplement contribution

Keep food adequacy and supplement contribution separate.

For example, display concepts equivalent to:

```text
Zinc from planned food: 8.0 mg/day
Dietary reference target: 11.0 mg/day
Dietary gap: 3.0 mg/day
Physician-ordered supplement contribution: 5.0 mg/day
Combined planned exposure: 13.0 mg/day
```

The Food Planner must not intentionally lower food quality simply because an active supplement exists.

Supplement contribution may be included in a combined exposure/safety view after the physician order is active, but dietary adequacy must remain independently visible.

### 41.5 Relationship to weight-loss and other goal plans

For a calorie-deficit plan, Fitsho must not destroy the intended calorie deficit or macronutrient structure merely to force every micronutrient to an exact food-only target.

The planner should first make reasonable food-based improvements inside configured tolerances. If an important dietary gap remains, the gap is shown to the physician along with laboratory context when available. The physician decides whether no action, dietary modification, additional testing, follow-up, or a supplement order is appropriate.

This same principle applies to maintenance, weight gain, muscle gain, body recomposition, and other supported goals.

## 42. Simple user interface

The Nutrition UI should prioritize clarity over visual complexity.

### Main nutrition summary

Show prominently:

- Goal
- Estimated BMR
- Estimated TDEE
- Preferred calorie target
- Planned calorie average
- Preferred protein target
- Minimum acceptable protein
- Planned protein average
- Core micronutrient reference-policy version used for the plan
- Carbohydrate range and planned amount
- Fat range and planned amount
- Fibre target and planned amount
- Expandable core micronutrient adequacy summary
- Top unresolved micronutrient gaps and data-confidence warnings
- Selected main-meal count
- Selected snack count
- Budget
- Estimated weekly cost
- Budget gap or remaining amount
- Plan status
- Mandatory physician-review status
- Physician approval date and physician identity only after a real approval

A generated plan that has not yet been approved must be clearly labeled as a draft awaiting physician review and must not be presented as active. However, the complete draft must remain visible to the owning user immediately after generation. Pending physician review must never be implemented as a blank screen, hidden-plan state, or access denial for the user's own safe generated draft.

### Physician-review presentation

Before physician approval, show:

- The complete generated Nutrition plan.
- A prominent status such as `در انتظار بررسی پزشک`.
- No green physician-approved badge/checkmark.
- The current review state and any laboratory request.
- A short explanation that the displayed version was generated by Fitsho and has not yet been physician-approved.

After physician approval, show:

- A green physician-approved badge/checkmark.
- The exact approved plan revision.
- Approval date and physician identity according to product/privacy policy.
- Whether approval was `approved without plan changes` or `approved with physician changes`.
- A structured summary of physician changes when plan-defining content changed.
- All user-visible physician notes.
- Physician-added supplement orders and their instructions/status.
- A notification/history entry for the completed review.

If the physician requests laboratory information or changes, keep the current draft visible while clearly showing the new review state.

### Laboratory area

Provide a user-facing laboratory area that supports:

- Upload PDF/image
- List uploaded laboratory documents
- Show upload/test dates and review status
- Show physician requests for additional/repeat tests
- Delete or replace user-owned files when allowed by retention/audit policy
- Clearly distinguish `uploaded`, `reviewed`, and `requested` states

Do not show machine-generated diagnosis from a laboratory image.

### Per-meal view

For every meal or snack show:

- Slot role: main meal or snack
- Food names
- Exact grams, millilitres, or item counts
- Verified serving equivalents where supported
- Calories
- Protein
- Carbohydrates
- Fat
- Fibre
- Sodium
- Supported core micronutrients
- Other supported diet-quality values
- Estimated cost

### Ideal-versus-planned view

The user must be able to understand:

- What Fitsho considers the preferred target
- What the minimum acceptable value is
- What the current plan actually provides
- How far the current plan is from preferred
- Which constraint caused the difference
- Which core micronutrients are below their dietary reference target
- Whether a micronutrient repair was attempted and whether the gap remained because of budget, availability, medical policy, preference, or incomplete data

Never label a dietary-reference gap as a diagnosed vitamin or mineral deficiency.

### Supplement area

Show physician-managed supplement orders separately from the food plan, including:

- Supplement/active ingredient
- Physician-defined dose and frequency
- Start/end or duration when present
- User-facing instructions
- Status
- Linked reason or laboratory context when the physician marks it user-visible
- Food contribution versus supplement contribution versus combined exposure where data is reliable

The user may acknowledge, track, or report problems according to product policy, but must not directly edit the physician-defined dose or frequency.

### Calorie-counter experience

Keep the existing low-friction quick-check-in principles.

### Accessibility and responsiveness

The frontend must be:

- RTL-compatible
- Mobile-friendly
- Keyboard accessible where applicable
- Screen-reader aware
- Clear about loading, empty, blocked, pending-review, laboratory-request, and error states

## 43. API capabilities

Expose capabilities consistent with repository conventions.

### Unified profile

- Get profile
- Update shared fields
- Get capability completion state
- Change product mode

### Nutrition profile and safety

- Get nutrition profile
- Update budget
- Update main-meal count selection
- Update snack count selection
- Update liked foods
- Update disliked foods
- Update allergies and intolerances
- Update medical and dietary restrictions
- Run safety evaluation

### Estimates

- Get BMR/TDEE estimate
- Get calorie target
- Get macro and diet-quality targets
- Get selected micronutrient reference targets and reference kinds
- Get micronutrient adequacy and data-confidence summary
- Get preferred/minimum/planned comparison

### Plans

- Generate weekly draft plan
- Automatically submit otherwise eligible generated plan to physician review
- Get latest user-visible generated/reviewed plan regardless of approval state
- Get active physician-approved plan
- Get plan revision
- List plan history
- Get physician-review state
- Get physician approval metadata for the exact revision
- Get user-visible physician notes
- Get structured physician change summary between generated and approved revisions
- Get physician supplement orders associated with the current reviewed plan/user
- Preview meal removal
- Preview meal replacement
- Preview food replacement
- Lock/unlock meal
- Regenerate unlocked meals
- Confirm a user-requested revision and submit it for re-review
- Get exact-quantity shopping list
- Get nutrient-gap summary
- Get micronutrient-gap and repair summary
- Get budget-gap summary

### Foods and meals

- Search verified food catalogue
- Get food details
- Get serving conversions
- Get meal nutrient totals
- Get food price provenance

### Daily tracking

- Submit daily quick check-in
- Confirm planned meal
- Adjust actual consumed portion
- Skip meal
- Add outside-plan food
- List recent foods
- Create quick approximation
- Edit/delete own consumption entry
- Get daily summary
- Get history

### Photo estimation

- Upload food photo
- Get estimate
- Confirm/edit estimate
- Delete photo and derived estimate

### Laboratory records

- Create secure laboratory upload
- List user's laboratory documents
- Get user's own laboratory-document metadata
- Get secure user-authorized laboratory preview/download representation
- Delete or replace own laboratory document when policy permits
- List physician laboratory requests
- Submit a document in response to a physician request
- Get laboratory review status

### Physician review

- List authorized physician review queue
- Assign/claim review according to policy
- Get exact plan revision and snapshots
- Get authorized laboratory documents
- Request laboratory information
- Mark laboratory document reviewed
- Approve exact plan revision
- Reject exact plan revision
- Request changes
- Create physician structured plan revision
- Add professional notes
- Get review history

### Physician supplement orders

- Search verified supplement catalogue
- Create physician supplement-order draft
- Validate configured contraindications/interactions
- Prescribe/activate order through physician action
- Modify physician order
- Discontinue order
- Complete order
- Link laboratory document or dietary gap
- Request follow-up laboratory information
- Get user supplement-order history

Use ownership and role authorization on every endpoint.

## 44. Admin capabilities

Admin functionality should support:

- Verified food catalogue CRUD
- Food data import and validation
- Price providers
- Price mapping
- Price imports
- Manual price overrides
- Price freshness and provider-health visibility
- Scientific policy versions
- Micronutrient reference-policy versions and source registry
- Micronutrient optimization/repair weights and tolerances
- Safety policy versions
- Planner scoring and tolerance versions
- Medical-condition policies
- AI photo-estimation settings
- Physician role management
- Physician assignment and queue oversight
- Laboratory-document policy and retention settings
- Laboratory-request oversight without bypassing clinical authorization
- Review audit history
- Supplement catalogue and verification
- Physician supplement-order audit visibility

Admin actions affecting policy, roles, assignment, or safety must be audited.

Admin access does not automatically grant clinical authority to approve plans or prescribe supplement orders unless the same account separately has an authorized physician role.

## 45. Security, privacy, and ownership

Enforce:

- Authenticated ownership on user resources
- Explicit physician authorization for clinical records
- Secret encryption for AI API keys
- Masked secrets in UI and API responses
- Secure food-photo upload validation
- Secure laboratory PDF/image upload validation
- Malware/type/size validation appropriate to the storage stack
- Private storage for laboratory documents
- Signed, temporary, or otherwise access-controlled laboratory file delivery
- Controlled laboratory retention and deletion policy
- Audit trails for physician access, plan approval, laboratory review, supplement orders, and policy changes
- No cross-user access to budgets, plans, logs, photos, laboratory files, medical data, supplement orders, or reviews
- Least-privilege access for admins and physicians

Laboratory documents and medical/nutritional data must not be sent to external AI providers by default.

The only external AI path allowed by this Nutrition specification remains the separately consented food-photo estimation flow. Laboratory images/PDFs must not be sent to OpenRouter under this specification.

Sensitive health details must not be unnecessarily logged. Audit logs should record actions and identifiers without copying entire laboratory contents or unnecessary medical free text.

## 46. Reproducibility and auditability

Every generated plan must be reproducible from its persisted snapshot.

Persist enough information to know:

- User input snapshot
- Goal
- Selected main-meal and snack buckets
- Effective main-meal and snack slot counts
- Meal-distribution policy version
- BMR/TDEE formula version
- Scientific policy version
- Micronutrient reference-policy version and exact selected reference rows
- Micronutrient optimization-policy version
- Micronutrient repair-policy version and accepted repair actions
- Safety policy version
- Food data versions and micronutrient data-completeness snapshot
- Price snapshot
- Price-selection version
- Planner version
- Planner weights/tolerances version
- Mandatory physician-review request ID and state
- Physician approval/rejection metadata for the exact revision
- Laboratory-document references included in the review snapshot
- Physician supplement-order references active at the time of the snapshot
- Generated meals and exact quantities
- Physician-edited meals/quantities when a new reviewed revision is created
- Nutrient totals
- Micronutrient adequacy statuses and unresolved gaps
- Budget totals
- Warnings and reason codes

Do not silently mutate an active historical plan when source food data or prices change.

---

## 47. Tests and documentation

### Backend unit tests

Cover at minimum:

- Age eligibility
- BMR formulas
- TDEE separation
- Goal-adjusted calorie targets
- Protein minimum and preferred targets
- Carbohydrate allocation
- Fat limits
- Fibre
- Sugar handling
- Sodium AI/CDRR semantics and absence of fabricated UL
- Micronutrient reference selection by age and sex
- RDA versus AI selection semantics
- EAR not treated as a personal hard minimum
- Nutrient-specific UL scope
- Potassium AI behavior and absence of fabricated healthy-population UL
- Vitamin D dietary-gap wording without deficiency diagnosis
- Iron vegetarian modifier only when explicitly applicable
- Folate DFE semantics
- Vitamin A RAE/source-form semantics when enabled
- Missing nutrient data
- Budget conversion
- Main-meal count validation and effective slot resolution
- Snack count validation and effective slot resolution
- Meal-distribution policy application
- Main-meal versus snack food-role validation
- Price normalization
- Quote selection
- Allergy and exclusion filtering
- Ideal-versus-achievable status
- Budget-constrained protein-source selection
- Nutrient gap calculations
- Micronutrient deficit scoring
- Micronutrient repair improves target nutrient without breaking macro tolerances
- Repair revalidates all nutrients and budget
- Repair iteration bound and anti-oscillation behavior
- Planner determinism
- Infeasible budget behavior
- Shopping-list aggregation
- Meal replacement validation
- Review invalidation and mandatory re-review for plan-defining changes only
- Consumption-only tracking changes do not invalidate plan approval
- Pending drafts cannot serve as `ON_PLAN`/`MOSTLY_ON_PLAN` tracking baselines
- Plan-derived tracking entries remain pinned to their source plan revision
- Allergy planning blocks remain strict while truthful actual-intake logging is allowed with warning
- Strict/flexible budget behavior and overage reporting
- Portion-feasibility warning behavior
- Automatic physician-review request creation for every generated eligible Nutrition plan
- Plan-state/review-state synchronization and same-session physician edit approval
- Activation effective-date behavior and atomic single-active-plan supersession
- Concurrent user/physician edit conflict and stale `plan_revision_id` rejection
- Single current pending-review lineage and superseded-review invalidation
- `CHANGES_REQUESTED` next-action transitions
- Generation-outcome separation from successful plan lifecycle
- Candidate-level missing-price filtering and insufficient price-coverage failure
- Macro-energy hard-minimum infeasibility and `TARGET_INFEASIBLE` behavior
- Protein reference-mass policy selection when high adiposity/body-composition uncertainty applies
- Fibre soft-by-default versus explicit medical-policy hard behavior
- Laboratory upload ownership and secure access
- Laboratory-request state transitions
- Physician plan approval gate
- Physician structured edit followed by deterministic revalidation
- Physician supplement-order lifecycle and audit metadata
- Pre-activation combined food-plus-supplement upper-limit safety gate
- Food-versus-supplement nutrient contribution separation
- Daily tracking confidence
- Photo-estimation mapping
- Supplement approval rules

### Backend API and integration tests

Cover:

- Ownership
- Product mode
- Unified profile
- Two-question meal-structure onboarding
- Two-question food-preference onboarding
- Safety flow
- Nutrition estimates
- Micronutrient target/adequacy endpoints
- Plan generation
- Price unavailable flow
- Exact quantities
- Shopping list
- Meal edits
- Tracking
- Photo estimation
- Mandatory physician review
- Laboratory upload and physician laboratory request flow
- Physician supplement-order workflow
- Supplement workflow

### Frontend tests

Cover:

- Conditional onboarding
- The two required meal-structure questions with the approved options
- Only the two approved ordinary food-preference questions in Nutrition onboarding
- Main-meal and snack count questions
- Like/dislike food questions
- Budget entry in IRR
- Safety states
- Goal and nutrient summary
- Micronutrient adequacy summary and non-diagnostic wording
- Ideal-versus-planned gap display
- Per-main-meal and per-snack grams and nutrient breakdown
- Correct number of generated main-meal and snack slots
- Shopping list
- Plan editing
- Daily quick check-in
- Photo correction flow
- Mandatory physician review status
- Pending-review draft remains fully visible to the owning user
- No green physician-approved badge/checkmark before approval
- Green physician-approved badge/checkmark after real approval
- Approved revision replaces the default current-plan view without erasing the original generated revision
- Physician change summary when the approved revision differs from the generated revision
- User-visible physician notes and strict hiding of internal notes
- Physician-added supplement orders visible after they are created/prescribed according to workflow
- Laboratory upload/request status while the draft remains visible
- Physician supplement-order status
- Mobile/RTL behavior

### Documentation

Maintain:

- `docs/nutrition-implementation-design.md`
- Scientific policy documentation
- Micronutrient source registry, DRI semantics, and reference-table documentation
- Micronutrient optimization and repair documentation
- Food-data provenance documentation
- Price-provider and freshness documentation
- Planner scoring/tolerance documentation
- Medical-condition policy documentation
- Photo privacy and OpenRouter integration documentation
- Mandatory physician review, laboratory-record, and physician supplement-order documentation
- API documentation
- Migration notes for the rewritten Nutrition scope

Use authoritative scientific and official technical sources.

Do not invent references.

---

## 48. Staged implementation tasks

### Task 0 - Repository audit, provider research, and approved implementation design

**Status: COMPLETED before this rewrite. Do not rerun.**

Preserve the approved scientific-policy table, planner tolerances, price rules, and medical-condition classification unless an explicit conflict with this rewritten specification requires a documented update.

---

### Task 1 - Product mode and unified profile foundation

**Status: COMPLETED before this rewrite. Do not rerun.**

Preserve backward compatibility.

---

### Task 2 - Early age, safety, medical-condition, and nutrition-profile foundation

**Status: COMPLETED before this rewrite. Do not rerun.**

Some previously introduced fields are now outside Nutrition scope and must be handled by Task 2A.

---

### Task 2A - Nutrition-scope cleanup and migration

Implement before Task 3:

- Inspect exactly which out-of-scope fields, enums, schemas, endpoints, UI questions, tests, and completion requirements were added by Task 2.
- Remove those questions from Nutrition onboarding.
- Remove them from Nutrition completion requirements.
- Remove them from Nutrition planner input contracts.
- Keep or safely deprecate existing database columns if destructive removal would risk user data.
- Add backward-compatible migrations only where necessary.
- Ensure Nutrition adds and requires exactly two meal-structure questions:
  - usual number of main meals
  - usual number of snacks
- Ensure Nutrition ordinary food-preference onboarding still has only:
  - foods the user likes
  - foods the user dislikes
- Add typed meal-count buckets and effective planner slot-count semantics without reintroducing Cooking fields.
- Preserve separate safety questions for allergies, intolerances, medical restrictions, and cultural/religious exclusions.
- Add/normalize structured dietary-pattern and smoking-status data only where required by approved micronutrient policy; collect them in the early Step 5 safety/nutrition context, keep them outside ordinary likes/dislikes questions, and do not duplicate them later.
- Persist resolved liked/disliked foods as catalogue references when possible, with unresolved text kept non-scoring until deterministic mapping.
- Preserve the individual monthly food budget and all medical/safety information.
- Update APIs, schemas, frontend, tests, and documentation.

Commit, push, report, and stop.

---

### Task 2B - Authoritative micronutrient policy and source foundation

Implement before Task 3 because micronutrient-aware planning was added after the original Task 0 approval:

- Research and document the applicable NASEM DRI reference tables for the supported adult population.
- Cross-check the selected values and nutrient-specific semantics against NIH ODS Health Professional Fact Sheets.
- Create the versioned micronutrient source registry.
- Create normalized `RDA`, `AI`, `EAR`, `UL`, `CDRR`, and medical-override semantics.
- Seed or import the supported adult micronutrient reference rows with provenance.
- Preserve age 18 as its correct DRI age group rather than silently treating every adult-age user as 19+.
- Define nutrient-specific units and forms, including mg, mcg, mcg DFE, mcg RAE, and vitamin D mcg/IU conversion where required.
- Define UL scope semantics so food-only, supplement-only, and nutrient-form-specific limits are not confused.
- Define sodium AI/CDRR behavior and potassium AI behavior under the 2019 NASEM report.
- Define medical-policy override precedence.
- Define core micronutrient adequacy scoring, aggregation windows, completeness thresholds, and repair tolerances.
- Add explicit policy that a dietary-reference gap is not a diagnosis of deficiency.
- Document the USDA FoodData Central mapping strategy for food composition; do not use USDA food data as the source of human requirement targets.
- Add unit and policy tests using authoritative sanity-check values documented in Section 17.

Do not implement full meal-plan micronutrient optimization in this task.

Commit, push, report, and stop.

---

### Task 3 - Scientific energy and nutrient-target engine

Implement only under approved Task 0 scientific policy:

- Daily non-exercise activity
- Structured exercise
- Reuse of training data for `BOTH` with explicit bootstrap/fallback precedence
- Nutrition-only exercise questions
- Versioned goal-to-energy/protein policy mapping
- Joint/iterative macro-range resolution without unchecked carbohydrate residual logic
- BMR
- Non-exercise energy estimate
- Exercise-energy estimate
- TDEE without double counting
- Goal-adjusted calorie target
- Support for weight loss, weight gain, muscle gain, body recomposition, fat loss, and maintenance through repository-compatible goal modeling
- Protein minimum
- Protein preferred target
- Versioned protein reference-mass method for high-adiposity or unreliable-body-composition cases
- Carbohydrate range
- Total-fat range
- Fibre adequacy target and policy-defined hard minimum only when applicable
- Joint/iterative macro-energy feasibility validation with structured `TARGET_INFEASIBLE` behavior
- Free-sugar limit
- Added-sugar handling
- Saturated-fat limit
- Trans-fat limit
- Sodium AI/CDRR policy semantics
- Core micronutrient reference selection from the approved Task 2B policy
- Nutrient-specific RDA/AI/UL/CDRR metadata
- Ideal/minimum/planned target structure
- Explanation metadata
- Confidence states
- Formula and policy versions
- Estimate API
- Scientific documentation
- Tests

Commit, push, report, and stop.

---

### Task 4 - Verified food catalogue and structured meal composition

Implement:

- Food models
- Core macronutrients
- Fibre
- Total, added, and free sugar
- Saturated and unsaturated fats where available
- Trans fat
- Sodium
- Core micronutrient composition fields required by the approved micronutrient policy
- Extended micronutrient fields when reliable data is available
- Per-nutrient source, unit, form, missing-data, and confidence metadata
- USDA FoodData Central import/mapping support where appropriate
- Canonical quantity semantics
- Units and verified conversions
- Nutrition-data provenance
- Missing-data handling
- Verification status
- Import validation
- Limited verified seed data
- Foods common in Iran
- Structured meal composition with exact quantities
- `MAIN_MEAL` and `SNACK` slot-role modeling
- Verified food/composition eligibility for main-meal versus snack use
- Deterministic slot-role taxonomy for substantial main proteins, main staple carbohydrates, snack foods, and flexible complements
- Per-meal and per-snack nutrient totals
- Food APIs
- Admin food CRUD
- Tests


Commit, push, report, and stop.

---

### Task 5 - Live multi-provider food-price system

Implement only after approved Task 0 price policy:

- Provider protocol
- Provider models
- Provider mapping
- Database-managed provider
- Validated import provider
- Development-only seed provider
- Any approved permitted external adapters
- Price normalization
- Optional reliable minimum-purchase/package metadata for `expected_purchase_outlay` without turning the planner into a package-count recommender
- Live-price states
- Freshness rules
- Candidate-level missing-price exclusion rules
- Minimum candidate-pool price-coverage requirements and `INSUFFICIENT_PRICE_COVERAGE` behavior
- Minimum-source requirements
- Staleness
- Outlier handling
- Deterministic quote selection
- Manual override
- Health status
- Provenance
- Admin APIs and pages
- Snapshot foundation
- Contract tests
- Strict `LIVE_PRICE_UNAVAILABLE` behavior

Do not use undocumented retailer APIs.

Do not claim stale or seed prices are live.

Commit, push, report, and stop.

---

### Task 6 - Scientific weekly budget-aware planner

Implement:

- Weekly plan model
- Plan days, main meals, and snacks
- User-selected main-meal and snack slot counts as planner inputs
- Versioned nutrient-distribution across selected slots
- Input snapshots
- Price snapshots
- Deterministic planner
- Allergy filtering
- Medical-condition policy enforcement
- Nutrient optimization
- Core micronutrient adequacy optimization from the start of candidate scoring
- Bounded targeted micronutrient repair pass
- Full post-repair revalidation
- Nutrient-specific UL/CDRR and medical-override enforcement
- Micronutrient data-completeness handling
- Diet-quality validation
- Explicit `STRICT` versus `FLEXIBLE` budget behavior
- Budget optimization
- Portion-feasibility validation under versioned policy
- Ideal/minimum/planned comparison
- Main-meal protein-source combination selection
- Snack candidate selection from snack-eligible foods
- Carbohydrate-source allocation
- Fat-source allocation
- Planner tolerances and scoring
- Separation of successful plan lifecycle from `FAILED` / `SAFETY_BLOCKED` / `INFEASIBLE` / `TARGET_INFEASIBLE` / `LIVE_PRICE_UNAVAILABLE` generation outcomes
- Repetition control
- Ingredient reuse when economically useful
- Respectful budget explanations
- Nutrient-gap explanations
- Micronutrient-gap and repair explanations without deficiency diagnosis
- Structured `INFEASIBLE`, `TARGET_INFEASIBLE`, and `LIVE_PRICE_UNAVAILABLE` generation outcomes rather than activatable plan states
- Plan generation
- History
- Mandatory physician-review activation gate
- Not-yet-active but fully user-visible drafts for every otherwise eligible generated Nutrition plan
- Immutability tests

Commit, push, report, and stop.

---

### Task 7 - Exact-quantity shopping list and plan editing

Implement:

- Exact required-quantity shopping-list aggregation
- Canonical quantity semantics
- Nutritional contribution per item
- Exact-quantity cost calculation
- No package-count recommendation
- Meal removal preview
- Meal replacement
- Food replacement
- Meal locking
- Partial regeneration
- Change confirmation
- Explicit `CONSUMPTION_ONLY` versus `PLAN_CONTROL_METADATA` versus `PLAN_DEFINING` semantics
- Immutable revisions for plan-defining changes
- Recalculated nutrition and cost
- Review invalidation and mandatory re-review only for plan-defining revisions
- Optimistic-concurrency / expected-revision protection for plan-defining edits and approval actions
- Block user plan-defining edits/regeneration while the physician review is actively `IN_REVIEW`, while keeping consumption tracking available
- At most one current nonterminal review lineage per user, with superseded pending drafts preserved in history and old reviews invalidated
- Automatic physician-review request creation for every generated eligible Nutrition plan
- Laboratory upload ownership and secure access
- Laboratory-request state transitions
- Physician plan approval gate
- Physician structured edit followed by deterministic revalidation
- Physician supplement-order lifecycle and audit metadata
- Food-versus-supplement nutrient contribution separation
- Meal feedback
- Reuse of previous plan with recalculation
- APIs
- Tests

Commit, push, report, and stop.

---

### Task 8 - Low-friction calorie counter and food outside the plan

Implement:

- Daily quick check-in
- `ON_PLAN`, `MOSTLY_ON_PLAN`, `OFF_PLAN`, and `NOT_RECORDED`
- One-tap approximate confirmation of planned intake from the active physician-approved revision only
- Plan-revision ID pinned on plan-derived tracking entries
- Manual/photo actual-intake logging allowed while a draft is pending review
- Allergy/hard-exclusion warning semantics for truthful actual-intake logging
- Deviation-only flow
- Optional detailed planned-meal tracking
- Food outside the plan from the catalogue
- Recent-food quick add
- Approximate structured quick add
- Entry source and confidence
- Edit and delete
- Planned-versus-actual calculations
- Daily summaries
- Date-range consumption history
- Optional reminder setting
- APIs
- Functional RTL frontend
- Tests

Do not require the user to log every food every day.

Do not assume an unconfirmed planned meal was eaten.

Commit, push, report, and stop.

---

### Task 9 - OpenRouter photo-based food estimation

Implement the previously approved photo-estimation flow only.

OpenRouter must not be introduced into any other nutrition calculation or planning path.

Commit, push, report, and stop.

---

### Task 10 - Adherence, charts, history, and adaptive planning

Implement:

- Calorie adherence
- Protein adherence
- Meal adherence
- Budget adherence where data supports it
- Tracking completeness
- Confidence-aware metrics
- `INSUFFICIENT_DATA` behavior
- Transparent optional composite score
- Planned-versus-actual charts
- Weekly trends
- History filters
- Weight trend beside adherence without causal claims
- Adaptive food and meal preferences based on user feedback
- Safeguards against automatic target changes
- User-confirmed target-update flow
- Tests

Commit, push, report, and stop.

---

### Task 11 - Laboratory records, mandatory physician review, and physician panel

Implement:

- `PHYSICIAN` role and authorization if not already fully implemented
- Secure user laboratory PDF/image uploads
- Laboratory document metadata and ownership
- Private file access and retention controls
- Physician laboratory requests and statuses
- Physician assignment and review queues with minimal priority/timing/reassignment/overdue metadata
- Explicit plan-state ↔ review-state transition mapping
- Same-session physician edit -> revalidation -> approval path for the newly created revision
- Explicit `CHANGES_REQUESTED` next-action transitions
- Concurrent user/physician revision protection and stale-revision rejection
- Deterministic activation transaction using effective start date, one active baseline per overlapping date range, and atomic supersession of the previous active revision
- Automatic review-request creation for every otherwise eligible generated Nutrition plan
- Mandatory not-yet-active `PENDING_PHYSICIAN_REVIEW` plan state
- Immediate owning-user visibility of the complete pending-review draft
- Explicit separation of plan visibility from physician approval/activation state
- No physician-approved green badge/checkmark before real approval
- Exact plan-revision viewer
- Medical/safety profile snapshot viewer
- Laboratory-document viewer
- Micronutrient adequacy and unresolved-gap viewer
- Deterministic validation viewer
- Budget and price-provenance viewer
- Structured plan editor
- Approve, reject, request-changes, and request-lab-information actions
- New immutable revision creation after physician edits
- Deterministic revalidation after physician edits
- Approval valid only for the exact revision
- Automatic approval invalidation for changed plan revisions
- Activation only after real physician approval
- Green physician-approved badge/checkmark only after real approval
- Approved-current-plan presentation using the exact approved revision
- Structured user-facing physician change summary when the physician changes plan-defining content
- Physician and user notifications required by the workflow
- User-visible and internal physician notes with strict separation
- User access to user-visible physician notes after review
- Review history and audit trail preserving original generated and physician-approved revisions
- APIs
- RTL physician frontend
- Ownership, authorization, workflow, upload, and approval-gate tests

Laboratory uploads are available to every Nutrition user but are not automatically mandatory for every user. The physician may require additional or repeat tests before approval when clinically appropriate.

Do not diagnose from an uploaded image using OpenRouter.

Do not claim physician approval before a real authorized physician action.

Commit, push, report, and stop.

---

### Task 12 - Physician-managed supplement workflow

Implement:

- Verified supplement catalogue and nutrient/active-ingredient metadata
- Structured `PhysicianSupplementOrder`
- Draft, prescribed, active, completed, discontinued, and cancelled states
- Physician-only authority to create the final active supplement order in this Nutrition workflow
- Dose, unit, frequency, duration/date, instructions, and rationale fields
- Optional links to dietary micronutrient gaps
- Optional links to laboratory documents
- Optional follow-up laboratory requests
- Configured contraindication, allergen, interaction, and upper-bound checks
- Mandatory pre-activation combined food-plus-supplement exposure safety check
- Structured hard block when a proposed order violates an applicable hard upper limit
- Visibility of current medications and relevant conditions to the physician
- Food-versus-supplement nutrient contribution separation
- Combined exposure/safety summary after an order is active
- User-facing supplement plan and history
- Immediate display of physician-created/prescribed supplement orders in the user's reviewed-plan experience, with dose, frequency, duration/date, instructions, rationale when user-visible, and status
- Clear indication of which supplement orders were added or changed during the current physician review
- User acknowledgement/adherence fields if implemented, without allowing the user to edit physician dose/frequency
- Physician modification and discontinuation workflow
- Audit trail
- Admin supplement catalogue CRUD and verification
- APIs
- Physician, admin, and user frontend flows
- Tests

The Nutrition planner must never automatically prescribe a supplement from a dietary gap or laboratory upload.

Do not prescribe or alter prescription medication through the supplement workflow.

Commit, push, report, and stop.

---

### Task 13 - Coordinated functional Nutrition frontend

Complete and coordinate:

- Guided conditional onboarding
- Early safety flow
- Two meal-structure questions with the approved options
- Two ordinary food-preference questions only
- Budget input
- Nutrition profile
- Review-required and blocked pages
- Fully visible generated plan while status is `PENDING_PHYSICIAN_REVIEW`, `PHYSICIAN_REVIEW_IN_PROGRESS`, or `AWAITING_LAB_INFORMATION`
- Clear message that a pending draft is visible but is not the `ON_PLAN` adherence baseline until physician-approved/active
- Pending-review banner/status with no green approval badge before real physician approval
- Green physician-approved badge/checkmark after approval
- Physician approval date/identity presentation according to privacy policy
- Approved revision view and structured physician-change summary
- User-visible physician notes
- Physician-added supplement orders integrated into the reviewed-plan experience
- Energy and nutrient estimates
- Goal-specific target explanation
- Core micronutrient adequacy summary
- Micronutrient reference kind, gap, data confidence, and repair explanation
- Non-diagnostic wording for low dietary micronutrient intake
- Ideal/minimum/planned comparison
- Weekly plan
- Correct user-selected number of main-meal and snack slots
- Per-main-meal and per-snack exact quantities
- Per-main-meal and per-snack calorie, protein, carbohydrate, fat, fibre, sodium, and supported diet-quality totals
- Live-price status
- Exact-quantity shopping list with pending-review purchase warning until physician approval
- Capability-state mapping (`NUTRITION_PENDING_REVIEW`, `NUTRITION_READY`, `BOTH_READY`) derived from authoritative plan/review lifecycle
- Meal details
- Removal and replacement previews
- Meal locking
- Partial regeneration
- Budget summary
- Meal feedback
- Daily quick check-in
- Food outside plan
- Photo estimation
- Planned-versus-actual summary
- Adherence charts and history
- Automatic mandatory physician-review request and status
- User laboratory upload area and physician laboratory requests
- Physician supplement-order status, instructions, and history
- Coordinated training and nutrition dashboard
- Admin pages
- Physician panel with plan, laboratory, and supplement workspaces
- RTL
- i18n
- Mobile responsiveness
- Accessibility
- Loading, empty, and error states
- Frontend tests


Commit, push, report, and stop.

---

### Task 14 - Security, privacy, reliability, and observability hardening

Implement or verify:

- Ownership checks
- Role permissions
- Secret encryption
- API-key masking
- Food-image privacy and retention
- Laboratory-document privacy, retention, and access control
- Signed or temporary food-image access
- Signed or temporary laboratory-document access
- Upload validation
- Rate limiting where supported
- Idempotency
- Duplicate prevention
- Background-job retries
- Provider health metrics
- AI usage and error metrics
- Physician review, laboratory access, and supplement-order audit logs
- Security tests
- Privacy documentation

Commit, push, report, and stop.

---

### Task 15 - Final validation and documentation

Complete all documentation.

Update the root README and environment documentation.

Run repository-equivalent checks, including at minimum:

#### Backend

```bash
pytest
ruff check
mypy
```

#### Frontend

```bash
npm test
npm run lint
npm run build
```

Also verify:

- Alembic heads
- Upgrade from the previous production migration
- Fresh database migration from zero to head
- Existing workout tests
- Nutrition acceptance scenarios
- Review authorization scenarios
- OpenRouter-disabled behavior
- Live-price unavailable behavior
- No generated or uncommitted artifacts

Fix all newly introduced failures.

Commit, push, report, and stop.

---

## 49. Main acceptance scenarios

### Existing training user

- Existing user remains compatible with prior `TRAINING` migration.
- Workout functionality continues unchanged.
- Nutrition is optional.

### Nutrition-only onboarding

- Shared fields are entered once.
- User is not forced through training-only questions.
- Minimum exercise information is collected for energy estimation.
- User selects usual main meals from `2`, `3`, or `4 or more`.
- User selects usual snacks from `0`, `1`, `2`, or `3 or more`.
- Ordinary food-preference onboarding asks only what foods the user likes and dislikes.
- Allergies/intolerances and other safety restrictions are collected early once, then reviewed/confirmed later without a duplicate questionnaire.
- Dietary pattern and smoking status, when required by enabled nutrient policy, are collected inside the early safety/nutrition step with an `UNKNOWN`/decline option.
- Meal-structure selections are persisted and affect generated plan slots.

### User-selected meal distribution

- A user selecting `3` main meals and `2` snacks receives three `MAIN_MEAL` slots and two `SNACK` slots per planned day.
- The scientific daily targets are calculated before slot distribution.
- Calories and nutrients are distributed across the selected structure according to versioned policy.
- Main meals receive substantial meal compositions; snacks use snack-eligible foods.
- A substantial chicken/meat/fish plus rice/potato-style plate never appears as a snack.
- Zero-snack selection produces no snack slots.
- The planner does not lower daily scientific targets merely because fewer slots were selected.
- Open-ended selections persist their bucket and the effective slot count used in the plan snapshot.

### Goal-specific calculation

- User selects a supported primary goal.
- The system calculates estimated energy needs and goal-adjusted targets under approved policy.
- Protein, carbohydrate, fat, fibre, and diet-quality targets are visible.
- Hard macronutrient minima cannot silently exceed the calorie target; preferred targets are relaxed first, policy-approved calorie adjustment is used only when allowed, otherwise generation returns `TARGET_INFEASIBLE`.
- Protein calculations use the versioned reference-mass method rather than blindly using total body weight when high adiposity or unreliable body-composition data requires another approved method.

### Micronutrient-aware planning

- The user's applicable core micronutrient references are selected from a versioned authoritative policy using age, sex, and explicitly known supported modifiers.
- A 19+ male receives the approved zinc RDA reference for males; a 19+ female receives the approved female reference.
- Potassium is represented using AI rather than a fabricated RDA.
- Sodium uses AI/CDRR semantics rather than a fabricated toxicity UL.
- The planner considers micronutrient adequacy while scoring candidates, not only after a macro-only plan is finalized.
- If zinc or another core micronutrient remains low, the planner attempts a bounded targeted substitution or portion adjustment.
- A repair that increases zinc but breaks calorie, protein, another hard nutrient limit, medical safety, or budget is rejected or rebalanced.
- All nutrients and cost are recalculated after an accepted repair.
- If the gap remains, the user sees the dietary-reference gap and reason without being told they are clinically deficient.
- Vitamin D dietary intake below RDA is not presented as proof of vitamin D deficiency.
- Missing micronutrient composition data reduces confidence rather than being treated as zero.

### Ideal versus achievable

- Preferred target, minimum acceptable value, planned value, and gap are shown separately.
- The system never reports a preferred target as achieved when the budget-constrained plan falls short.

### Protein-source allocation

- The planner evaluates multiple verified compatible protein sources.
- It may combine chicken, meat, eggs, dairy, legumes, soy, fish, or other verified foods.
- It considers total nutritional quality and cost, not only cheapest protein-per-gram.

### Exact daily meals

- User sees exact food quantities for each meal.
- Each meal shows calories, protein, carbohydrates, fat, fibre, sodium, and supported micronutrient values where data confidence permits.
- The plan provides a weekly or rolling-average micronutrient adequacy summary rather than requiring every micronutrient to hit an exact number in every single meal.
- Daily and weekly totals match item-level calculations.

### Adequate budget

- Plan satisfies configured tolerances.
- Weekly cost fits the budget.
- Shopping-list totals match the plan.

### Limited but feasible budget

- Economical substitutions are used.
- Preferred and planned protein are shown honestly.
- User receives respectful trade-off explanations.

### Infeasible budget

- Generation returns `INFEASIBLE`; it does not create a physician-reviewable plan revision.
- An unsafe/inadequate plan is not activated.
- Budget gap and limiting constraints are shown.

### Allergy

- An allergen appears in no generated meal, substitute, shopping recommendation, or incompatible supplement product.
- If the user actually consumed an excluded/allergenic food, truthful manual/photo-confirmed logging is allowed with a prominent safety warning; logging reality never makes the food eligible for future planning.

### Mandatory physician review for every Nutrition plan

- Every otherwise supported generated Nutrition plan becomes a not-yet-active physician-review draft.
- The complete generated draft is immediately visible to the owning user.
- A standard-risk user is not auto-activated.
- The plan enters `PENDING_PHYSICIAN_REVIEW`, but this state does not hide the plan from the user.
- The user can view the full meals, snacks, quantities, nutrients, micronutrient analysis, budget, shopping list, and review status while waiting.
- Before approval, no green physician-approved badge/checkmark is shown.
- A real authorized physician reviews the exact revision.
- Approval applies only to that exact revision.
- Only a physician-approved exact revision may become active.
- An approved revision whose effective start date is future remains `PHYSICIAN_APPROVED` until that date; otherwise activation occurs immediately after approval.
- Only one revision is the current active adherence baseline for an overlapping date range, and activating a replacement atomically supersedes the prior active revision while preserving history.
- While a physician has a review actively `IN_REVIEW`, user plan-defining edits/regeneration are blocked; consumption tracking remains available and stale revision mutations are rejected.
- The user has at most one current nonterminal review lineage; a newer allowed user-generated revision supersedes the prior pending draft and invalidates its old review.
- After approval, the user sees a green physician-approved badge/checkmark, approval metadata, the exact approved revision, user-visible physician notes, and physician-added supplement orders.
- If the physician changed the plan, the user sees a structured summary of changes from the originally generated revision to the approved revision.
- If the physician requests laboratory information, the current draft remains visible while the status changes to `AWAITING_LAB_INFORMATION`.
- A later plan-defining edit invalidates approval and requires re-review; the changed draft remains visible with the new pending-review state.

### Laboratory upload and request

- Every Nutrition user has access to a secure laboratory area.
- A user may upload PDF/JPG/PNG laboratory documents.
- Laboratory upload is not automatically mandatory for every user.
- A physician may request additional or repeat laboratory information before approval.
- If required information is missing, the plan remains not activated in `AWAITING_LAB_INFORMATION` but the current generated draft remains fully visible to the owning user together with the physician laboratory request.
- The physician can review the original secure document.
- OpenRouter does not diagnose the laboratory image.
- Machine extraction, if added later, is never treated as physician-confirmed until explicitly reviewed.

### Micronutrient gap and physician supplement order

- The planner first attempts food-based micronutrient optimization and bounded repair.
- It does not destroy calorie-deficit, macro, safety, meal-role, or budget constraints merely to force every dietary micronutrient to an exact target.
- An unresolved dietary gap is shown to the physician without claiming clinical deficiency.
- The physician sees relevant laboratory documents and medical context.
- Only the physician may create the active supplement order in this Nutrition workflow.
- The physician may instead choose no action, dietary modification, more testing, or follow-up.
- Food contribution and supplement contribution remain separately visible.
- The active supplement order does not cause the planner to intentionally lower food quality.

### Live price

- A plan labeled as using live prices has fresh, traceable, policy-compliant quotes for every selected food.
- Provider and effective date are visible.
- A food with no valid required price is excluded as a candidate rather than poisoning unrelated priced candidates.
- If missing prices make the remaining candidate pool insufficient under configured coverage rules, generation returns `LIVE_PRICE_UNAVAILABLE` with `INSUFFICIENT_PRICE_COVERAGE`.

### Exact-quantity shopping list

- User sees exact required quantities such as `2.3 kg` of chicken.
- User sees nutritional contribution and exact-quantity cost.
- A pending-review draft shopping list is visible but clearly warns that the plan may change and final purchasing should follow physician approval.
- Fitsho does not recommend a number of commercial packages.

### One-tap on-plan check-in

- `ON_PLAN`/`MOSTLY_ON_PLAN` use only the physician-approved active revision effective for that date.
- A pending visible draft cannot prefill adherence tracking.
- User confirms the day with one action.
- Planned meals become approximate actual entries.
- Entries are labeled as estimated from the plan and keep the source plan revision ID.

### Photo estimation

- AI result is shown as an estimate.
- User must confirm or edit it.
- Unconfirmed output is not logged.
- Verified food data produces final numeric totals after mapping.
- A user-confirmed allergenic/excluded food may be recorded as actual intake with a safety warning, but remains forbidden for planning/recommendation.

### Backward compatibility

- Existing workout APIs and tests continue to pass.
- Existing users are not forced to complete Nutrition onboarding.
- Task 2A removes out-of-scope Nutrition questions without destructive data loss.

---

## 50. Final quality rules

- Safety over aggressive targets
- Evidence over assumptions
- Deterministic calculations over AI guesses
- OpenRouter only for photo-based food estimation
- User confirmation before AI estimates enter history
- Explainability over opaque optimization
- Nutritional adequacy over cheapest-food optimization
- Authoritative DRI references over invented micronutrient targets
- RDA/AI/UL/CDRR semantics over one generic minimum/maximum model
- Constraint-aware micronutrient optimization over generate-reject-regenerate loops
- Targeted bounded repair over full-plan random regeneration
- Non-diagnostic dietary-gap wording over false deficiency claims
- Nutrient-specific upper-limit scope over naive universal ceilings
- Preferred/minimum/planned separation over misleading success claims
- User-selected meal structure over planner-invented meal counts
- Role-appropriate main meals and snacks over undifferentiated eating slots
- Exact food quantities over vague meal descriptions
- Low-friction tracking over burdensome daily diaries
- Active approved revision as the adherence baseline over tracking against unapproved drafts
- Truthful actual-intake logging over pretending a consumed allergen did not occur
- Approximate honesty over false precision
- Backward compatibility over broad rewrites
- Valid provider abstractions over website coupling
- Fresh traceable prices over fake live-price claims
- Exact required quantities over package-count advice
- Transparent infeasibility over unsafe plans
- Generation failures/infeasibility as explicit outcomes over fake lifecycle states
- One current review lineage and revision-safe concurrency over competing drafts and stale approvals
- Deterministic effective-date activation over ambiguous `PHYSICIAN_APPROVED -> ACTIVE` behavior
- Mandatory real physician approval for every active Nutrition plan over automatic activation
- Secure original laboratory records over AI-only interpretation
- Physician clinical judgment over automatic supplement prescription
- Food-first micronutrient repair before supplement escalation
- Separate food adequacy and supplement contribution over hidden combined totals
- Physician-only clinical authority for supplement orders
- No fabricated nutritional values
- No fabricated prices
- No fabricated professional approval
- No automatic transition between tasks
