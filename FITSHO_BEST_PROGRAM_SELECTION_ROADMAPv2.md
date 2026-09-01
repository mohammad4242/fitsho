# نقشه اجرایی نهایی برای Luna Max — انتخاب بهترین برنامه Fitsho

## دستور مستقیم به Luna Max

تو Luna Max هستی و باید این برنامه را در مسیر زیر اجرا کنی:

`/home/mohammad/project/fitsho`

تا وقتی کاربر صریحاً نگفته است «تأیید است، اجرا کن»، هیچ فایل یا کدی را تغییر نده.

بعد از تأیید:

- کار را مرحله‌به‌مرحله و تا پایان ادامه بده.
- از subagent استفاده نکن.
- هر مرحله را جداگانه با TDD اجرا کن.
- وارد مرحله بعد نشو مگر اینکه تست‌های مرحله فعلی پاس شده باشند.
- تغییرات نامرتبط و فایل‌های untracked کاربر را لمس نکن.
- هرگز از `git add -A` یا `git add .` استفاده نکن.
- فقط فایل‌های همان مرحله را stage کن.
- هیچ قانون ایمنی یا علمی را برای بالا بردن درصد موفقیت ضعیف نکن.
- اگر به شکاف واقعی کاتالوگ تمرین رسیدی، برنامه جعلی نساز و توقف را صادقانه گزارش کن.
- بعد از هر مرحله، commit متمرکز و Conventional Commit بساز و در صورت فعال بودن remote، branch فعلی را push کن.
- فقط در صورت blocker واقعی، تصمیم محصولی جدید یا شکست verification متوقف شو.

گزارش هر مرحله دقیقاً با این قالب باشد:

```text
Changed:
Verified:
Git:
Next:
```

قبل از commit، پیام پیشنهادی commit را در بخش `Git:` نشان بده. سپس چون اجرای خودکار تأیید شده است، commit و push را انجام بده و نتیجه واقعی را گزارش کن.

---

# ۱. ارزیابی رودمپ فعلی

اصل معماری رودمپ درست است:

> موتور باید چند برنامه کامل و معتبر بسازد و بهترین آن‌ها را انتخاب کند؛ نه اولین برنامه‌ای را که موفق می‌شود.

اما رودمپ فعلی به‌تنهایی برای پیاده‌سازی امن کافی نیست و چند قسمت آن با کد فعلی هماهنگ نیست یا بیش از حد ساده شده است.

## موارد درست رودمپ

- جداسازی پیشنهاد کاندیدا، ساخت کامل و انتخاب نهایی درست است.
- templateها و canonical splitها باید در یک استخر اصلی رقابت کنند.
- dynamic fallback باید fallback باقی بماند.
- کاندیدای hard-invalid نباید وارد مقایسه شود.
- امتیاز نهایی نباید weighted average ساده باشد.
- رتبه قبل از ساخت فقط باید برای shortlist و tie-break استفاده شود.
- `template_survival.py` باید شواهد feasibility را حفظ کند، اما تصمیم‌گیر نهایی نباشد.
- trace انتخاب نهایی ضروری است.

## اختلاف‌های رودمپ با repository فعلی

- پایین‌تر بودن مدت جلسه از بازه ترجیحی از قبل soft شده است. این تغییر در commitهای اخیر انجام شده و نباید دوباره پیاده‌سازی شود.
- `engine.py` در مسیر exact split و dynamic fallback هنوز اولین موفقیت را return می‌کند.
- templateها چند بار ساخته می‌شوند، اما:
  - با `candidate_survival_sort_key(...)` انتخاب می‌شوند؛
  - بر اساس product score زود prune می‌شوند؛
  - پس از موفقیت template، canonical splitها فرصت رقابت ندارند.
- `coach_quality.py` برای انتخاب نهایی کافی نیست:
  - volume را با `actual_effective_volume` می‌سنجد، درحالی‌که validation برای بعضی عضلات از direct volume استفاده می‌کند.
  - priority فقط effective sets را می‌سنجد و direct target و frequency را نادیده می‌گیرد.
  - recovery تقریباً binary است و repairable conflict می‌تواند امتیاز ۱۰۰ بگیرد.
  - coverage برای splitهای غیر full-body معمولاً `not_applicable` است.
  - warningها بدون توجه به hard/repairable/soft شمرده می‌شوند.
  - substitution فقط از template adaptation خوانده می‌شود.
- `_post_construction_repair_events(...)` در `engine.py` بر اساس جست‌وجوی کلمات داخل trace کار می‌کند و قابل اتکا نیست.
- `CoachQualityMetricsResponse` در بخش review، فیلدهای اضافه داخلی را با `extra="forbid"` رد می‌کند. اضافه شدن metrics جدید بدون اصلاح projection می‌تواند خروجی Coach review را مخفی کند.
- تغییر انتخاب بهترین برنامه به‌تنهایی success rate را از وضعیت فعلی به بالای ۹۰٪ نمی‌رساند. شکست‌های exercise count، required slot و semantic opener باید جداگانه و بدون تضعیف safety اصلاح شوند.
- benchmarkهای قدیمی Phase 11 مربوط به snapshotهای قدیمی کاتالوگ هستند و baseline فعلی محسوب نمی‌شوند.

## وضعیت فعلی قابل اتکا

- branch فعلی: `main`
- HEAD فعلی: `0da6cbf`
- `origin/main` نیز روی همین commit است.
- worktree تعداد زیادی فایل untracked متعلق به کاربر دارد؛ همه باید حفظ شوند.
- آخرین اجرای کامل Program Engine قبل از commit صرفاً گزارشی اخیر: `1286 passed`.
- commit اخیر فقط اسکریپت audit را تغییر داده است؛ بااین‌حال Luna باید baseline را دوباره اجرا کند.
- audit فعلی ۱۰۰ پروفایل تقریباً ۴۹ موفقیت از ۹۸ پروفایل supported نشان می‌دهد؛ بنابراین وضعیت فعلی نزدیک ۵۰٪ است، نه ۹۰٪.
- بیشترین failureهای فعلی با این کدها هم‌پوشانی دارند:
  - `SESSION_EXERCISE_COUNT_OUT_OF_RANGE`
  - `REQUIRED_SLOT_HARD_IMPOSSIBILITY`
  - `SEMANTIC_OPENER_CONFLICT`

---

# ۲. تصمیم‌های معماری که با تأیید این پلن قفل می‌شوند

## استخر کاندیدا

Options:

1. Unified bounded primary pool + separate dynamic fallback — Recommended
2. انتخاب برنده هر خانواده و سپس مقایسه برندگان
3. یک استخر جهانی شامل dynamic fallback

انتخاب این پلن: گزینه ۱.

## روش امتیازدهی

Options:

1. Lexicographic max-min quality key — Recommended
2. Pareto frontier
3. Weighted average score

انتخاب این پلن: گزینه ۱.

## اصلاح انتخاب greedy تمرین

Options:

1. Beam search محدود، فقط بعد از اثبات greedy dead-end — Recommended
2. حفظ کامل greedy فعلی
3. جست‌وجوی ترکیبی سراسری

انتخاب این پلن: گزینه ۱.

---

# ۳. معماری نهایی

```text
Request
  ↓
Normalization / Safety / Eligibility
  ↓
Pre-construction ranking
  ├── حداکثر ۶ template واجد شرایط
  └── حداکثر ۶ canonical split
  ↓
ساخت کامل و مستقل هر کاندیدا
  ↓
Repair / Prescription / Volume / Recovery
  ↓
Validation
  ↓
Final Gate
  ↓
حذف تمام کاندیداهای hard-invalid یا دارای evidence ناقص
  ↓
Lexicographic post-construction selection
  ↓
BEST PRIMARY PROGRAM

فقط اگر هیچ primary candidate معتبر نبود:

Dynamic fallback ranking
  ↓
ساخت ۶ کاندیدای اول
  ↓
اگر هیچ‌کدام معتبر نبودند، ساخت حداکثر ۶ کاندیدای بعدی
  ↓
انتخاب بهترین dynamic candidate معتبر
```

محدودیت قطعی:

- حداکثر primary candidate ساخته‌شده: ۱۲
- حداکثر dynamic candidate: ۱۲
- حداکثر کل در بدترین درخواست: ۲۴
- ساخت کاندیداها sequential و deterministic باشد.
- parallel construction در این نسخه ممنوع است.
- eligibility، catalog و session capacity یک‌بار محاسبه و به‌صورت immutable بین کاندیداها reuse شوند.
- هیچ pruning بر اساس product score پس از ورود کاندیدا به shortlist انجام نشود.
- فقط duplicate دقیق شناسه در همان خانواده قبل از ساخت حذف شود.

---

# ۴. قرارداد انتخاب نهایی

## فایل اصلی جدید

`backend/app/workouts/program_engine/program_selection.py`

انواع داخلی زیر ساخته شوند:

- `CandidateSource`
  - `TEMPLATE`
  - `CANONICAL_SPLIT`
  - `DYNAMIC_FALLBACK`
- `ProgramCandidate`
- `ProgramQualityView`
- `CandidateComparison`
- `ProgramSelectionDecision`

`ProgramCandidate` حداقل این اطلاعات را داشته باشد:

- source
- identifier پایدار
- preconstruction rank
- preconstruction score فقط برای trace
- generation result
- repair event tokens
- actual substitution count
- source metadata محدود و بدون اطلاعات شخصی

## شرایط ورود به مقایسه

یک کاندیدا فقط وقتی قابل مقایسه است که:

- `result.is_success` درست باشد.
- `result.program` وجود داشته باشد.
- validation error نداشته باشد.
- trace نهایی `final_quality_gate` وجود داشته باشد.
- final gate وضعیت accepted یا accepted-with-constraints داشته باشد.
- `coach_quality_v2` کامل باشد.
- هیچ warning با classification نوع hard نداشته باشد.
- تمام warning codeها classification شناخته‌شده داشته باشند.

اگر warning ناشناخته یا quality evidence ناقص بود:

- کاندیدا حذف شود.
- دلیل `PROGRAM_SELECTION_EVIDENCE_MISSING` یا `PROGRAM_SELECTION_UNKNOWN_CONSTRAINT` ثبت شود.
- اگر همه کاندیداها به این دلیل حذف شدند، موتور fail closed کند و برنامه اول را به‌عنوان fallback برنگرداند.

## کلید lexicographic

Weighted average ساخته نشود.

ترتیب مقایسه:

1. hard validity یک شرط ورود است، نه امتیاز.
2. coverage status:
   - satisfied
   - proven constrained
3. `critical_floor`: ضعیف‌ترین بُعد قابل‌اعمال.
4. آرایه مرتب‌شده ابعاد مهم از ضعیف‌ترین به قوی‌ترین.
5. explicit priority satisfaction، اگر برای پروفایل قابل‌اعمال است.
6. Body Analysis priority satisfaction، اگر قابل‌اعمال است.
7. volume floor و سپس volume median.
8. coverage percentage.
9. recovery margin.
10. semantic degradation burden.
11. warning burden به ترتیب:
    - repairable
    - soft
12. repair burden:
    - structural
    - workload
    - scheduling
    - total
13. actual substitution burden.
14. duration fit.
15. template preference فقط در tie واقعی کیفیت.
16. preconstruction rank فقط داخل همان خانواده.
17. identifier پایدار برای deterministic tie-break.

ابعاد `not_applicable` صفر نشوند. applicability باید از request تعیین شود و برای تمام کاندیداهای یک request یکسان باشد.

نمونه اجباری:

- برنامه با امتیازهای `100, 70, 100, 100`
- برنامه با امتیازهای `94, 94, 93, 100`

برنامه دوم باید انتخاب شود، چون ضعیف‌ترین بُعد آن بهتر است.

---

# ۵. فایل‌هایی که باید ساخته شوند

## فایل‌های قطعی

```text
backend/app/workouts/program_engine/program_selection.py
backend/app/workouts/program_engine/repair_observability.py
backend/app/workouts/program_engine/session_feasibility.py

backend/tests/workouts/program_engine/test_program_selection.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_session_feasibility.py

backend/scripts/program_engine_audit_support.py
backend/scripts/audit_supported_profile_catalog.py
backend/tests/workouts/program_engine/test_program_engine_audit_support.py
```

## فایل‌های مشروط

فقط اگر audit ثابت کرد required slot به علت انتخاب greedy قبلی از دست می‌رود:

```text
backend/app/workouts/program_engine/session_search.py
backend/tests/workouts/program_engine/test_session_search.py
```

اگر این مدرک وجود نداشت، این دو فایل ساخته نشوند.

---

# ۶. فایل‌ها و قسمت‌های دقیق برای تغییر

## انتخاب و orchestration

### `backend/app/workouts/program_engine/engine.py`

تغییر در:

- `generate_program(...)`
- حلقه template candidateها
- حلقه exact-day splitها
- حلقه dynamic fallbackها
- `_post_construction_repair_events(...)`
- `_finalize_program(...)`
- `_volume_range_metric(...)`
- helper مربوط به append کردن trace روی نتیجه موفق

رفتار جدید:

- template موفق فوراً return نشود.
- exact split موفق فوراً return نشود.
- dynamic fallback موفق فوراً return نشود.
- product-score early pruning حذف شود.
- template و canonical split در primary pool مشترک قرار گیرند.
- dynamic در pool جدا بماند.
- خطاهای candidateهای شکست‌خورده حفظ شوند، اما روی candidate موفق دیگر به‌عنوان failure آن candidate نوشته نشوند.
- trace انتخاب نهایی فقط به برنامه برنده اضافه شود.
- `actual_constraint_volume` به volume metrics اضافه شود.

## کیفیت واقعی پس از ساخت

### `backend/app/workouts/program_engine/coach_quality.py`

تغییر در:

- `build_coach_quality_metrics(...)`
- `_target_satisfaction(...)`
- `_volume_fit(...)`
- recovery fit
- duration fit
- coverage normalization
- substitution extraction

خروجی قبلی برای compatibility حفظ شود و این موارد اضافه شوند:

```text
schema_version = coach_quality_v2
selection_quality:
  critical_dimensions
  coverage_percentage
  volume_floor
  volume_median
  explicit_priority_floor
  body_analysis_priority_floor
  recovery_margin
  duration_fit
  semantic_degradation
```

قواعد:

- volume از `actual_constraint_volume` استفاده کند.
- priority برای هر عضله، ضعیف‌ترین نسبت direct/effective/frequency باشد.
- explicit priority و Body Analysis جدا بمانند.
- recovery از نسبت actual gap به required gap استفاده کند.
- coverage تمام splitها را از evidence موجود volume/required coverage استخراج کند.
- full-body coverage همچنان قرارداد سخت قبلی خود را حفظ کند.
- duration فقط quality tie-break باشد.
- average بالا نتواند یک عضله یا اولویت بسیار ضعیف را مخفی کند.

## repair observability

### `backend/app/workouts/program_engine/repair_observability.py`

- repairها را با exact stage/reason-code allowlist ثبت کند.
- جست‌وجوی substringهایی مانند `ADDED` یا `REPLACED` حذف شود.
- repairها به این دسته‌ها تقسیم شوند:
  - structural
  - workload
  - scheduling
- normalization معمولی یا traceهای informational repair محسوب نشوند.
- actual template substitution جدا از structural repair نگهداری شود.
- substitution candidate یا fallback option، actual substitution حساب نشود.

### `backend/app/workouts/program_engine/template_survival.py`

- `CandidateSurvival` و شواهد آن حفظ شوند.
- `candidate_survival_sort_key(...)` می‌تواند برای trace template باقی بماند.
- دیگر برنده نهایی template یا کل برنامه را تعیین نکند.
- هیچ safety classification تغییر نکند.

## warning classification

### `backend/app/workouts/program_engine/constraint_classification.py`

- تمام warning/reason codeهای نهایی فعلی classification صریح بگیرند.
- موارد ناشناخته در selection fail closed شوند.
- کدهای جدید selection و constrained session اضافه شوند.
- `SESSION_EXERCISE_COUNT_OUT_OF_RANGE` بدون evidence و بعد از repair exhaustion همچنان hard باشد.
- کد constrained-session معتبر soft/constraint باشد، نه hard failure.

## recovery

### `backend/app/workouts/program_engine/recovery.py`

- helper واحد برای تبدیل `RecoveryAssessment` به recovery quality اضافه شود.
- hard recovery conflict همچنان باعث حذف candidate شود.
- repairable conflict امتیاز کامل نگیرد.
- validation و final gate همچنان از منبع فعلی recovery استفاده کنند.

## semantic opener

### `backend/app/workouts/program_engine/session_structure.py`

تغییر فقط در:

- `_semantic_order_rank(...)`
- `_is_required_semantic_opener(...)`
- `_semantic_ordering_errors(...)`

وقتی push-up و pull-up هر دو در یک جلسه هستند:

- فقط یکی required opener باشد.
- دیگری حذف نشود.
- انتخاب opener به ترتیب زیر باشد:
  1. strength-primary واقعی
  2. explicit chest/back priority
  3. ترتیب ساخت اولیه
  4. شناسه پایدار تمرین
- حرکت دوم با ترتیب عادی semantic قرار گیرد.
- semantic duplicate protection ضعیف نشود.

## حداقل تعداد تمرین با evidence

### `backend/app/workouts/program_engine/session_feasibility.py`

یک منبع واحد برای اثبات کمبود ظرفیت مفید بساز.

Evidence حداقل شامل این موارد باشد:

- day index
- actual MAIN count
- preferred minimum
- absolute hard minimum
- required slots satisfied
- تعداد exerciseهای بررسی‌شده
- دلیل رد exerciseهای قابل افزودن
- duration capacity blockers
- hard-volume blockers
- recovery blockers
- semantic/coherence blockers
- stable reason codes

قانون count:

- جلسه ۳۰ دقیقه: همان ۳ تا ۴ MAIN حفظ شود.
- جلسه ۴۰ یا ۴۵ دقیقه:
  - preferred minimum برابر سیاست فعلی بماند.
  - absolute minimum برابر ۳، فقط با evidence کامل.
- جلسه ۶۰ دقیقه یا بیشتر:
  - preferred minimum برابر سیاست فعلی بماند.
  - absolute minimum برابر ۴، فقط با evidence کامل.
- کمتر از absolute minimum همیشه hard failure باشد.
- Core، cardio و warm-up در MAIN count محاسبه نشوند.
- اگر exercise ایمن، مفید، غیرتکراری و قابل‌افزودن وجود دارد، evidence معتبر نیست.
- برنامه کم‌تعداد با evidence معتبر `accepted_with_constraints` شود و در final selection جریمه بگیرد.
- هیچ تمرین یا set بی‌فایده برای پر کردن عدد یا زمان اضافه نشود.

### فایل‌های مصرف‌کننده این policy

```text
backend/app/workouts/program_engine/duration_policy.py
backend/app/workouts/program_engine/duration_capacity.py
backend/app/workouts/program_engine/session_builder.py
backend/app/workouts/program_engine/session_duration.py
backend/app/workouts/program_engine/validation.py
backend/app/workouts/program_engine/final_gate.py
```

همه باید از `session_feasibility.py` استفاده کنند؛ منطق count در چند فایل دوباره نوشته نشود.

## compatibility بخش Coach review

### `backend/app/workout_reviews/coach_quality.py`

- قبل از validation، فقط فیلدهای عمومی تعریف‌شده در response schema را استخراج کند.
- metrics داخلی جدید باعث `None` شدن کل Coach projection نشوند.

### `backend/app/workout_reviews/schemas.py`

- فقط در صورت نیاز برای schema version یا فیلد عمومی جدید تغییر کند.
- `selection_quality` داخلی لازم نیست وارد API عمومی شود.

## versionها

### `backend/app/workouts/program_engine/rulesets/resistance_training_v1.py`

بعد از عبور کامل acceptance:

- `engine_version`: از `program_engine_v1` به `program_engine_v2`
- `version`: از `resistance_training_v5` به `resistance_training_v6`

این تغییر باید فقط در مرحله release انجام شود، نه ابتدای کار.

### تغییر تست نسخه

فایل زیر به‌صورت هدفمند rename شود:

```text
backend/tests/workouts/program_engine/test_ruleset_version_v5.py
→ backend/tests/workouts/program_engine/test_ruleset_version_v6.py
```

برنامه‌های ذخیره‌شده قدیمی تغییر نکنند. generation signature جدید باید فقط generationهای بعدی را invalidate کند. migration دیتابیس لازم نیست.

## فایل‌هایی که نباید برای selection بازنویسی شوند

```text
backend/app/workouts/program_engine/split_selector.py
backend/app/workouts/program_engine/template_selector.py
backend/app/workouts/program_engine/volume_planner.py
backend/app/workouts/program_engine/volume_repair.py
backend/app/workouts/program_engine/schemas.py
```

فقط اگر تست مشخصی نیاز واقعی را ثابت کرد، تغییر کوچک و مستقیم مجاز است.

---

# ۷. ترتیب اجرای دقیق

## مرحله ۰ — Freeze و baseline

هیچ فایل tracked تغییر نده.

کارها:

1. `AGENTS.md` را کامل بخوان.
2. `git status --short`، branch، HEAD و remote را ثبت کن.
3. فهرست فایل‌های untracked را به‌عنوان work متعلق به کاربر حفظ کن.
4. suite فعلی Program Engine را اجرا کن.
5. audit فعلی ۱۰۰ پروفایل را با seed موجود اجرا کن.
6. benchmark مستقل Phase 11.6 را روی ۱۵۰ پروفایل supported اجرا کن.
7. گزارش ۲۰۰ پروفایل فعلی را اجرا کن.
8. زمان p50 و p95 generation را ثبت کن.
9. تعداد exerciseها، templateها و hash ورودی benchmark را ثبت کن.
10. برای هر برنامه موفق فعلی این موارد را ذخیره کن:
    - اولین candidate موفق
    - source و identifier
    - split
    - quality metrics
    - warnings
    - repairها
    - runtime
11. artifactها را فقط زیر `backend/var/audits/best-program-selection/` نگهدار؛ commit نکن.

گیت:

- اگر suite فعلی سبز نیست، implementation را شروع نکن.
- شکست baseline را از regression جدید جدا گزارش کن.

Commit: ندارد.

---

## مرحله ۱ — selector خالص و deterministic

فایل‌ها:

```text
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_program_selection.py
```

ترتیب:

1. ابتدا تست‌های failing مربوط به selector را بنویس.
2. فقط pure types، admission و lexicographic selection را پیاده کن.
3. هنوز `engine.py` را تغییر نده.
4. تست‌ها باید این موارد را پوشش دهند:
   - hard-invalid هرگز برنده نشود.
   - candidate متعادل، candidate با یک ضعف جدی را شکست دهد.
   - N/A صفر نشود.
   - warning ناشناخته candidate را حذف کند.
   - warning کمتر در quality tie برنده شود.
   - repair کمتر در quality tie برنده شود.
   - substitution کمتر در quality tie برنده شود.
   - duration فقط tie-break نرم باشد.
   - template فقط در tie واقعی برنده شود.
   - نتیجه با تغییر ترتیب input ثابت بماند.
   - identifier پایدار tie نهایی را حل کند.

گیت:

- unit test جدید
- Ruff
- mypy فایل جدید
- `git diff --check`

Commit:

`feat(program-engine): add deterministic best-program selector`

---

## مرحله ۲ — Coach Quality v2 و repair evidence

فایل‌ها:

```text
backend/app/workouts/program_engine/coach_quality.py
backend/app/workouts/program_engine/repair_observability.py
backend/app/workouts/program_engine/recovery.py
backend/app/workouts/program_engine/constraint_classification.py
backend/app/workouts/program_engine/engine.py
backend/app/workout_reviews/coach_quality.py
backend/tests/workouts/program_engine/test_coach_quality_regressions.py
backend/tests/workouts/program_engine/test_validation_quality.py
backend/tests/workouts/program_engine/test_recovery_exposure_load.py
backend/tests/workouts/program_engine/test_constraint_classification.py
backend/tests/workout_reviews/test_coach_quality_projection.py
```

ترتیب:

1. ابتدا تست mismatch بین direct/effective volume را failing کن.
2. تست direct/effective/frequency priority را اضافه کن.
3. تست recovery margin را اضافه کن.
4. تست coverage غیر full-body را اضافه کن.
5. تست exact repair-code collection را اضافه کن.
6. تست projection با metrics اضافه داخلی را اضافه کن.
7. `actual_constraint_volume` را در `_volume_range_metric(...)` اضافه کن.
8. `coach_quality_v2` را بساز.
9. substring repair parser را با collector صریح جایگزین کن.
10. public Coach projection را backward-compatible نگهدار.

گیت:

- تمام تست‌های quality/recovery/classification/review
- Program Engine suite کامل
- Ruff، mypy و diff check

Commit:

`feat(program-engine): add robust post-construction quality evidence`

---

## مرحله ۳ — حذف first-success در canonical splitها

فایل‌ها:

```text
backend/app/workouts/program_engine/engine.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
backend/tests/workouts/program_engine/test_selection_sessions.py
```

ترتیب:

1. integration test بساز که split اول و دوم هر دو موفق‌اند ولی دومی کیفیت واقعی بهتری دارد.
2. ثابت کن تست روی کد فعلی fail می‌شود.
3. exact splitهای موفق را جمع‌آوری کن.
4. همه canonical splitهای shortlist را کامل بساز.
5. بهترین candidate را با selector انتخاب کن.
6. reason code مربوط به fallback را فقط وقتی اضافه کن که قبلی واقعاً fail شده باشد.
7. برای مقایسه بعد از موفقیت قبلی از reason code جدید استفاده کن:
   - `SPLIT_CANDIDATE_EVALUATED_FOR_QUALITY`
8. failureهای قبلی را به‌عنوان failure برنامه موفق بعدی ثبت نکن.

گیت:

- integration جدید
- تست‌های split/session
- Program Engine suite کامل
- deterministic repeated test

Commit:

`feat(program-engine): select the best valid canonical program`

---

## مرحله ۴ — استخر مشترک template و canonical

فایل‌ها:

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/template_survival.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_template_reference.py
backend/tests/workouts/program_engine/test_professional_topology_integration.py
backend/tests/workouts/program_engine/test_post_construction_feasibility.py
```

ترتیب:

1. تستی اضافه کن که template و canonical هر دو موفق‌اند و canonical با کیفیت بهتر برنده می‌شود.
2. تست tie واقعی بنویس که template برنده شود.
3. تست template با pre-score کمتر ولی final quality بهتر بنویس.
4. return نهایی template را از قبل canonical loop حذف کن.
5. product-score early pruning را حذف کن.
6. حداکثر ۶ template واجد شرایط را کامل بساز.
7. template و canonical را داخل primary pool مشترک قرار بده.
8. survival key فقط در trace بماند.
9. raw product score بین template و canonical مقایسه نشود.
10. بهترین primary candidate را انتخاب و سپس return کن.

گیت:

- template/professional topology tests
- integration selection tests
- Program Engine suite کامل
- اجرای چندباره با input order متفاوت

Commit:

`feat(program-engine): compare templates and canonical programs by final quality`

---

## مرحله ۵ — dynamic fallback و decision trace

فایل‌ها:

```text
backend/app/workouts/program_engine/engine.py
backend/app/workouts/program_engine/program_selection.py
backend/tests/workouts/program_engine/test_best_program_selection_integration.py
backend/tests/workouts/program_engine/test_template_selection_trace.py
backend/tests/workouts/program_engine/test_golden_scenarios.py
```

ترتیب:

1. تست کن که با primary معتبر، dynamic اصلاً اجرا نشود.
2. تست کن که با شکست همه primaryها، چند dynamic candidate ساخته شوند.
3. شش dynamic candidate اول را ارزیابی کن.
4. اگر هیچ‌کدام valid نبودند، حداکثر شش candidate بعدی را ارزیابی کن.
5. بهترین dynamic ساخته‌شده را انتخاب کن، نه اولین موفق را.
6. trace جدید با schema پایدار بساز.

Trace باید شامل این موارد باشد:

- `schema_version`
- selection phase
- selection strategy
- proposed count
- evaluated count
- successful count
- admitted count
- evidence-rejected count
- first-valid identifier
- selected identifier
- selected source
- selected preconstruction rank
- `selected_different_from_first_valid`
- quality key خلاصه
- warning/repair/substitution burden
- failure reason codeهای candidateهای ردشده

Trace نباید شامل این موارد باشد:

- برنامه کامل candidateهای بازنده
- اطلاعات هویتی یا پزشکی کاربر
- exercise list کامل candidateهای بازنده
- objectهای غیرقابل serialization

گیت:

- trace deterministic
- JSON serialization
- dynamic integration tests
- Program Engine suite کامل

Commit:

`feat(program-engine): select and trace the best dynamic fallback`

---

## مرحله ۶ — ابزار audit واحد

فایل‌ها:

```text
backend/scripts/program_engine_audit_support.py
backend/scripts/audit_supported_profile_catalog.py
backend/scripts/generate_100_profiles_audit_report.py
backend/scripts/generate_200_profiles_eval.py
backend/tests/workouts/program_engine/test_program_engine_audit_support.py
```

ترتیب:

1. محاسبه success denominator را در helper مشترک قرار بده.
2. supported بودن را فقط با production compatibility rules تعیین کن.
3. profileهای unsupported را در negative cohort جدا کن.
4. catalog gap را از denominator supported حذف نکن.
5. audit جدید ۲۰۰ profile supported قطعی و deterministic تولید کند.
6. هر profile fingerprint پایدار داشته باشد.
7. auditها این فیلدها را گزارش کنند:
   - selected vs first-valid
   - candidate counts
   - source
   - quality floor
   - coverage
   - volume
   - explicit priority
   - Body Analysis priority
   - recovery
   - duration
   - warnings
   - repairs
   - substitutions
   - runtime
   - failure taxonomy
8. اسکریپت‌های ۱۰۰ و ۲۰۰ فعلی از helper مشترک استفاده کنند.
9. PDF/HTML presentation نباید منبع محاسبات باشد؛ JSON خام منبع اصلی باشد.

گیت:

- تست denominator
- تست unsupported separation
- تست deterministic profile fingerprints
- تست catalog gaps counted as supported failures
- اجرای کوچک smoke بدون تولید artifact tracked

Commit:

`feat(program-engine): add reproducible best-program audit metrics`

---

## مرحله ۷ — اصلاح semantic opener

فایل‌ها:

```text
backend/app/workouts/program_engine/session_structure.py
backend/tests/workouts/program_engine/test_task_d_session_openers.py
backend/tests/workouts/program_engine/test_session_structure.py
backend/tests/workouts/program_engine/test_stage9_home_limited_equipment.py
```

ترتیب:

1. ابتدا failure واقعی push-up + pull-up را بازتولید کن.
2. تست کن که هر دو حرکت مجازند ولی فقط یکی required opener است.
3. انتخاب opener را deterministic و مطابق اولویت تعریف‌شده کن.
4. semantic duplicate protection را دست‌نخورده نگهدار.
5. profileهای bodyweight بدون caution و با caution را تست کن.
6. بررسی کن برنامه unsafe یا duplicate برای بالا بردن success ساخته نشده باشد.

گیت:

- opener tests
- semantic duplicate tests
- home-limited tests
- Program Engine suite کامل
- audit ۱۰۰ profile و مقایسه failure taxonomy

Commit:

`fix(program-engine): resolve dual semantic opener conflicts deterministically`

---

## مرحله ۸ — اصلاح count proxy با evidence

فایل‌ها:

```text
backend/app/workouts/program_engine/session_feasibility.py
backend/app/workouts/program_engine/duration_policy.py
backend/app/workouts/program_engine/duration_capacity.py
backend/app/workouts/program_engine/session_builder.py
backend/app/workouts/program_engine/session_duration.py
backend/app/workouts/program_engine/validation.py
backend/app/workouts/program_engine/final_gate.py
backend/app/workouts/program_engine/constraint_classification.py
backend/tests/workouts/program_engine/test_session_feasibility.py
backend/tests/workouts/program_engine/test_session_exercise_count_policy.py
backend/tests/workouts/program_engine/test_duration_capacity.py
backend/tests/workouts/program_engine/test_main_training_duration_invariant.py
backend/tests/workouts/program_engine/test_task_i_final_gate.py
```

ترتیب:

1. failureهای count فعلی را با پروفایل ثابت بازتولید کن.
2. تست کن under-preferred count بدون evidence رد می‌شود.
3. تست کن under-preferred count با evidence کامل پذیرفته می‌شود.
4. تست کن وجود یک exercise ایمن و مفید evidence را باطل می‌کند.
5. تست کن Core/cardio/warm-up MAIN محسوب نمی‌شوند.
6. تست کن hard volume، recovery، duration maximum و prescription همچنان enforce می‌شوند.
7. policy مرکزی را بساز و تمام مصرف‌کنندگان را به آن متصل کن.
8. duplicate count logic را حذف کن.
9. constrained count را در quality selection جریمه کن.
10. برنامه‌های ۳۰ دقیقه را خارج از قرارداد ۳–۴ نبر.

گیت:

- تمام count/duration/final-gate tests
- no under-evidenced thin program
- Program Engine suite کامل
- audit ۱۰۰ و ۱۵۰ profile

Commit:

`fix(program-engine): allow only evidenced constrained session counts`

---

## مرحله ۹ — تشخیص catalog gap در برابر greedy dead-end

فایل‌ها:

```text
backend/scripts/audit_supported_profile_catalog.py
backend/app/workouts/program_engine/session_builder.py
```

برای هر `REQUIRED_SLOT_HARD_IMPOSSIBILITY` مشخص کن:

- در شروع جلسه exercise سازگار با SlotSpec وجود داشت یا نه.
- exercise توسط انتخاب قبلی مصرف یا semantic-block شده است یا نه.
- hard volume یا duration واقعاً مانع بوده است یا نه.
- محدودیت injury/equipment دلیل واقعی بوده است یا نه.
- یک alternative ordering می‌توانست تمام required slotها را پر کند یا نه.

### اگر greedy dead-end ثابت شد

فایل‌های زیر را بساز:

```text
backend/app/workouts/program_engine/session_search.py
backend/tests/workouts/program_engine/test_session_search.py
```

Search فقط برای required SlotSpecها باشد:

- beam width: ۸
- branch factor هر slot: حداکثر ۴
- ترتیب deterministic
- ابتدا hard compatibility
- سپس `SessionCoherence.placement_rank()`
- سپس semantic diversity
- سپس volume/duration headroom
- سپس stable exercise slug
- optional exerciseها فقط بعد از تکمیل required slotها اضافه شوند.
- اگر beam search جواب نداد، engine همان hard failure را برگرداند.

Commit در صورت اثبات:

`fix(program-engine): backtrack required slots when greedy selection blocks viability`

### اگر catalog gap واقعی بود

- exercise جعلی اضافه نکن.
- safety/equipment/slot requirement را ضعیف نکن.
- این failureها را supported failure حساب کن.
- با گزارش دقیق profile/slot/equipment gap متوقف شو.
- ارتقای کاتالوگ باید task جداگانه و با تأیید کاربر باشد.

---

## مرحله ۱۰ — ارزیابی نهایی کیفیت، موفقیت و performance

هیچ version bump انجام نده تا این مرحله پاس شود.

### تست‌ها

از `backend/` اجرا شوند:

```text
uv run pytest tests/workouts/program_engine -q
uv run pytest tests/workout_reviews -q
uv run pytest -q
uv run ruff check app tests scripts
uv run ruff format --check app tests scripts
uv run mypy app
git diff --check
```

اگر full backend شکست نامرتبط داشت:

- آن را اصلاح نکن.
- failure را با evidence از تغییرات این task جدا کن.
- تا تعیین وضعیت، release را complete اعلام نکن.

### benchmarkها

- frozen 100-profile baseline
- Phase 11.6 independent 150 supported holdout
- audit جدید 200 supported profile
- unsupported/red-flag negative cohort
- سه اجرای مستقل برای determinism
- ۳۰ پروفایل stratified برای مقایسه انسانی

### حداقل success rate

برای ۱۵۰ پروفایل supported:

- بیشتر از ۹۰٪: حداقل ۱۳۶ موفق
- هدف ۹۵٪: حداقل ۱۴۳ موفق

برای ۲۰۰ پروفایل supported:

- بیشتر از ۹۰٪: حداقل ۱۸۱ موفق
- هدف ۹۵٪: حداقل ۱۹۰ موفق

تعریف موفقیت:

- برنامه ساخته شده باشد.
- validation معتبر باشد.
- final gate پذیرفته باشد.
- selection evidence کامل باشد.

catalog gap در denominator supported به‌عنوان failure باقی بماند.

negative cohort:

- safety/red-flag/unsupported rejection correctness باید ۱۰۰٪ باشد.

### معیارهای کیفیت

برای تمام profileهایی که بیش از یک candidate معتبر دارند:

- quality key برنامه انتخاب‌شده نباید از first-valid بدتر باشد.
- hard violation برابر صفر باشد.
- p10 و median ضعیف‌ترین بُعد کیفیت نسبت به baseline کاهش پیدا نکند.
- explicit priority و Body Analysis priority کاهش معنادار نداشته باشند.
- volume floor و coverage کاهش نداشته باشند.
- recovery hard conflict برابر صفر باشد.
- برنامه thin بدون evidence برابر صفر باشد.
- semantic duplicate برابر صفر باشد.
- repetition بدون دلیل progression افزایش پیدا نکند.
- duration fit فقط در صورتی افت کند که کیفیت بالاتر دیگری به‌دست آمده باشد.
- تعداد repair/substitution و علت آن‌ها قابل ردیابی باشد.

### blind Coach review

۳۰ جفت برنامه baseline و نسخه جدید، بدون نشان دادن نام نسخه، بررسی شوند:

- ساختار هفتگی
- تناسب با هدف
- اولویت عضلات
- Body Analysis
- حجم
- ریکاوری
- تنوع
- تکرار
- مدت
- کیفیت prescription

نسخه جدید باید در اکثریت واضح بهتر یا برابر باشد و هیچ failure ایمنی نداشته باشد.

### performance

ثبت شود:

- candidateهای proposed/evaluated/successful
- p50 latency
- p95 latency
- trace size
- memory usage در صورت قابل‌اندازه‌گیری

گیت پیشنهادی:

- p50 بیشتر از ۲ برابر baseline نشود.
- p95 بیشتر از ۳ برابر baseline نشود.
- اگر بیشتر شد، ابتدا caching محاسبات immutable و حذف محاسبات تکراری انجام شود.
- candidate cap، safety یا quality برای حل latency بدون تأیید کاربر کاهش داده نشود.
- parallel construction بدون تصمیم معماری جدید اضافه نشود.

---

## مرحله ۱۱ — version bump و release commit

فقط اگر:

- تمام تست‌های مرتبط پاس شده‌اند؛
- full Program Engine سبز است؛
- hard violation صفر است؛
- success supported بالای ۹۰٪ است؛
- هدف ۹۵٪ یا بیشتر رسیده، یا فاصله باقی‌مانده صرفاً catalog gap مستند و مورد تأیید کاربر است؛
- quality regress نکرده است؛
- determinism سه اجرای مستقل پاس شده است.

تغییرها:

```text
program_engine_v1 → program_engine_v2
resistance_training_v5 → resistance_training_v6
```

تست کن:

- generation signature جدید ساخته می‌شود.
- برنامه‌های ذخیره‌شده قبلی قابل خواندن هستند.
- migration لازم نیست.
- cache برنامه قدیمی به‌اشتباه برای request جدید reuse نمی‌شود.

Commit:

`feat(program-engine): release best-program selection engine v2`

سپس branch فعلی را push کن.

اگر success کمتر از ۹۰٪ است، این مرحله انجام نشود و task کامل اعلام نشود.

---

# ۸. تست‌های اجباری

## انتخاب نهایی

- invalid candidate با soft score بالا نمی‌تواند برنده شود.
- candidate متعادل از candidate میانگین‌بالا با یک ضعف جدی بهتر است.
- N/A به صفر تبدیل نمی‌شود.
- انتخاب مستقل از ترتیب list است.
- template و canonical در quality واقعی رقابت می‌کنند.
- curated source فقط tie-break است.
- dynamic fallback وارد primary competition نمی‌شود.
- dynamic first-success حذف شده است.
- quality evidence ناقص fail closed می‌شود.
- warning ناشناخته fail closed می‌شود.

## کیفیت

- direct/effective volume semantics با validation یکی است.
- priority شامل direct، effective و frequency است.
- explicit و Body Analysis جدا هستند.
- recovery repairable امتیاز کامل نمی‌گیرد.
- coverage غیر full-body قابل سنجش است.
- duration نمی‌تواند ضعف volume/priority/recovery را جبران کند.
- actual substitution با substitution option اشتباه نمی‌شود.
- repair parser وابسته به متن آزاد نیست.

## ایمنی و قراردادهای سخت

- injury/caution
- equipment
- inactive/review-pending exercise
- hard weekly/session volume
- prescription validity
- required slot
- semantic duplicate
- recovery hard conflict
- exact requested days
- full-body hard coverage
- superset safety
- Core/supplemental count semantics

هیچ‌کدام نباید برای سبز کردن audit ضعیف شوند.

## موفقیت

ماتریس باید شامل این تنوع باشد:

- gym
- home bodyweight
- home dumbbell
- ۲ تا ۶ روز
- ۳۰، ۴۰/۴۵، ۶۰، ۷۵، ۹۰ و ۱۲۰ دقیقه
- first month تا advanced
- تمام goalهای supported
- explicit priorities
- Body Analysis priorities
- cautionهای supported
- recovery-limited profiles
- equipment-limited profiles

---

# ۹. ریسک‌ها و regressionهای مهم

- nondeterminism ناشی از iteration روی set/frozenset
- تغییر candidateها به‌علت state مشترک
- بزرگ شدن بیش از حد decision trace
- مقایسه raw score بین دو خانواده متفاوت
- انتخاب template صرفاً به دلیل curated بودن
- پنهان شدن یک ضعف با average
- شمردن trace informational به‌عنوان repair
- شمردن substitution option به‌عنوان actual substitution
- استفاده از effective sets در عضله‌ای که direct constraint دارد
- accepted-with-constraints بدون evidence
- پذیرش برنامه thin برای بالا بردن درصد
- تغییر denominator benchmark برای بهتر نشان دادن نتیجه
- استفاده از benchmark تاریخی به‌عنوان نتیجه فعلی
- شکستن Coach review projection با metrics جدید
- reuse شدن برنامه cacheشده با engine policy جدید
- افزایش latency به‌علت ساخت چند candidate
- تغییر تست‌ها فقط برای پاس شدن به‌جای اصلاح رفتار

---

# ۱۰. معیار خاتمه واقعی

کار فقط وقتی تمام است که:

- exact split دیگر first-success نباشد.
- template و canonical در primary pool مشترک رقابت کنند.
- dynamic fallback جدا بماند و بهترین fallback ساخته‌شده انتخاب شود.
- hard-invalid candidate هرگز وارد رقابت نشود.
- selection کاملاً deterministic باشد.
- trace توضیح دهد چرا برنده انتخاب شده است.
- quality انتخاب‌شده برای تمام multi-valid profileها از first-valid بدتر نباشد.
- برنامه unsafe، invalid، duplicate یا hard-volume violating تولید نشود.
- success rate پروفایل‌های supported بیشتر از ۹۰٪ باشد.
- هدف ترجیحی ۹۵٪ یا بیشتر باشد.
- thin/unexplained program صفر باشد.
- full tests، Ruff، mypy و auditهای مستقل پاس شده باشند.
- commitهای متمرکز و push واقعی انجام شده باشند.

اگر تنها مانع رسیدن به ۹۰٪ یا ۹۵٪ شکاف واقعی کاتالوگ است، Luna نباید قوانین علمی را ضعیف کند. باید task را با گزارش دقیق profile/slot/equipment gap متوقف کند و برای ارتقای کاتالوگ تأیید جداگانه بخواهد.

این متن پس از تأیید کاربر، دستور اجرای کامل و خودکار Luna Max است. پیش از تأیید صریح، Luna باید متوقف بماند و هیچ فایلی را تغییر ندهد.
