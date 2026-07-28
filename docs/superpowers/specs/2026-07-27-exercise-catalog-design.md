# طراحی کاتالوگ حرکات ورزشی فیتشو

تاریخ: ۱۴۰۵/۰۵/۰۵

## ۱. هدف و محدوده

این قابلیت یک منبع کنترل‌شده و فقط‌خواندنی از حرکات ورزشی ایجاد می‌کند. کاربر
واردشده با پروفایل تکمیل‌شده می‌تواند حرکات را براساس ناحیه بدن، عضله، تجهیزات،
سطح و عبارت جست‌وجو مرور کند و جزئیات اجرای ایمن هر حرکت را ببیند.

این مرحله شامل تولید برنامه تمرینی، AI، ثبت ست، نمودار پیشرفت یا تغذیه نیست. پنل
مدیریت و آپلود رسانه به قابلیت مستقل آینده `feature/exercise-admin` منتقل شده است.
برنامه‌های تمرینی آینده فقط به `exercises.id` ارجاع می‌دهند.

## ۲. تصمیم معماری

کاتالوگ به‌صورت ماژول مستقل `app/exercises` در modular monolith فعلی ساخته می‌شود.
مرزهای router، schema، service و model مانند ماژول profile حفظ می‌شوند.

گزینه‌های بررسی‌شده برای مجموعه‌های چندمقداری:

1. جدول‌های رابطه‌ای جدا برای عضلات فرعی و تجهیزات
2. آرایه‌های JSON
3. مدل ترکیبی

گزینه نخست انتخاب شد. عضلات فرعی و تجهیزات قابل فیلتر و قابل استفاده در برنامه‌های
آینده هستند؛ بنابراین در جدول‌های رابطه‌ای ذخیره می‌شوند. JSON پیاده‌سازی اولیه را
کوتاه‌تر می‌کرد، اما کنترل مقادیر، indexگذاری و queryهای آینده را ضعیف‌تر می‌کرد.
فهرست مراحل اجرا و نکات ایمنی query نمی‌شوند و به‌صورت آرایه ساخت‌یافته در ستون‌های
JSON ذخیره می‌شوند.

برای جایگزین‌ها نیز رابطه صریح انتخاب شد. فقط جایگزین‌های بررسی‌شده ثبت می‌شوند و
شباهت عضله به‌تنهایی به معنی قابل‌جایگزین‌بودن نیست. فیلدهای ساخت‌یافته عضله و
تجهیزات برای فیلتر پویا در آینده باقی می‌مانند.

## ۳. ساختار backend

```text
backend/app/exercises/
├── __init__.py
├── dependencies.py
├── enums.py
├── models.py
├── router.py
├── schemas.py
├── seed.py
├── seed_data.py
└── service.py
```

- `router` قرارداد HTTP و نگاشت خطا را مدیریت می‌کند.
- `schemas` validation فیلترها و پاسخ‌ها را نگه می‌دارد.
- `service` query، صفحه‌بندی و seed transaction را مدیریت می‌کند.
- `models` فقط نگاشت و constraintهای دیتابیس را تعریف می‌کند.
- `dependencies` وجود session و پروفایل تکمیل‌شده را کنترل می‌کند.
- `seed_data` داده‌های قابل بازبینی را از منطق واردکردن جدا می‌کند.
- `seed` فرمان مستقل `python -m app.exercises.seed` را فراهم می‌کند.

در `app.main` فقط router جدید ثبت می‌شود. seed هنگام startup اجرا نمی‌شود.

## ۴. مدل داده

### ۴.۱. جدول `exercises`

```text
id                    UUID, PK
slug                  VARCHAR(120), UNIQUE, NOT NULL
name_en               VARCHAR(160), NOT NULL
name_fa               VARCHAR(160), NOT NULL
body_region           VARCHAR, NOT NULL, CHECK
primary_muscle        VARCHAR, NOT NULL, CHECK
difficulty            VARCHAR, NOT NULL, CHECK
instructions_en       JSON, NOT NULL
instructions_fa       JSON, NOT NULL
safety_notes_en       JSON, NOT NULL
safety_notes_fa       JSON, NOT NULL
media_path            VARCHAR(255), NOT NULL
media_type            VARCHAR, NOT NULL, CHECK
media_source_url      VARCHAR(500), NULL
media_license         VARCHAR(120), NULL
media_attribution     VARCHAR(500), NULL
is_active             BOOLEAN, NOT NULL
created_at            TIMESTAMPTZ, NOT NULL
updated_at            TIMESTAMPTZ, NOT NULL
```

`slug` شناسه عمومی و ثابت URL است. `id` شناسه مرجع دامنه است. seed برای رکورد جدید
شناسه UUID قطعی مشتق‌شده از slug می‌سازد و اجرای مجدد، شناسه رکورد موجود را تغییر
نمی‌دهد.

روی `body_region`، `primary_muscle`، `difficulty` و `is_active` indexهای مناسب ایجاد
می‌شوند. جست‌وجوی اولیه با `ILIKE` روی slug و نام فارسی و انگلیسی انجام می‌شود؛ برای
مجموعه اولیه کوچک است و full-text search لازم نیست.

### ۴.۲. جدول `exercise_secondary_muscles`

```text
exercise_id     UUID, FK -> exercises.id, ON DELETE CASCADE
muscle          VARCHAR, CHECK
PRIMARY KEY (exercise_id, muscle)
```

### ۴.۳. جدول `exercise_equipment`

```text
exercise_id     UUID, FK -> exercises.id, ON DELETE CASCADE
equipment       VARCHAR, CHECK
PRIMARY KEY (exercise_id, equipment)
```

روی مقدار `muscle` و `equipment` index ساخته می‌شود تا فیلتر مستقیم کارآمد باشد.
primary muscle در جدول اصلی باقی می‌ماند، زیرا برای هر حرکت دقیقاً یک مقدار دارد.

### ۴.۴. جدول `exercise_alternatives`

```text
exercise_id                 UUID, FK -> exercises.id, ON DELETE CASCADE
alternative_exercise_id     UUID, FK -> exercises.id, ON DELETE CASCADE
reason_en                   VARCHAR(300), NOT NULL
reason_fa                   VARCHAR(300), NOT NULL
PRIMARY KEY (exercise_id, alternative_exercise_id)
CHECK (exercise_id <> alternative_exercise_id)
```

رابطه جهت‌دار است؛ هر جهت باید عمداً ثبت شود. این تصمیم اجازه می‌دهد دلیل جایگزینی
در دو جهت متفاوت باشد و از فرض برابری خودکار جلوگیری می‌کند.

### ۴.۵. مقادیر کنترل‌شده

`body_region`:

```text
upper_body
lower_body
core
```

`primary_muscle` و secondary muscle:

```text
chest
back
shoulders
biceps
triceps
traps
glutes
quadriceps
hamstrings
adductors
calves
abs
obliques
lower_back
```

`equipment`:

```text
bodyweight
dumbbell
barbell
cable
machine
resistance_band
bench
pull_up_bar
other
```

`difficulty`:

```text
beginner
intermediate
advanced
```

`media_type`:

```text
image
animated_webp
gif
video
placeholder
```

این مقادیر با `StrEnum` در application و `CHECK constraint` در دیتابیس کنترل
می‌شوند. lookup table اضافه نمی‌شود، زیرا taxonomy این مرحله ثابت و تحت کنترل کد
است.

## ۵. seed و رسانه

seed فقط شامل ۱۷ حرکت دارای GIF با نگاشت قطعی است:

```text
upper_body: 10
lower_body: 7
core: 0
```

توزیع اولیه:

```text
chest 1, back 1, shoulders 3, biceps 4, triceps 1, traps 0
glutes 1, quadriceps 4, hamstrings 1, adductors 0, calves 1
abs 0, obliques 0, lower_back 0
```

هر رکورد نام فارسی و انگلیسی، ۳ تا ۶ مرحله کوتاه، نکات ایمنی محافظه‌کارانه، عضلات،
تجهیزات و سطح دارد. محتوای حرکات پیش از ثبت از منابع معتبر بررسی می‌شود، ادعای
درمانی ندارد و جایگزین توصیه پزشکی نیست.

seed براساس slug رکوردها را upsert می‌کند، associationهای همان رکورد را همگام
می‌کند و داده‌های خارج از مجموعه seed را حذف نمی‌کند. اجرای دوم تعداد رکوردها یا
رابطه‌ها را افزایش نمی‌دهد. تنها رابطه جایگزین قطعی میان دو رکورد موجود،
`leg-press -> goblet-squat`، ثبت می‌شود.

در این مرحله هیچ رسانه‌ای از وب دانلود یا hotlink نمی‌شود. مالک پروژه یک بسته محلی
شامل ۲۷ GIF و ۶ JPEG ارائه و اجازه انتشار آن در مخزن را تأیید کرده است. فقط ۱۷ GIF
با تطبیق واضح حرکت، قالب معتبر و وضوح حداقل ۳۲۰ پیکسل وارد می‌شوند. فایل‌های JPEG،
تکراری، مبهم یا خارج از seed وارد مخزن نمی‌شوند.

نگاشت قطعی فایل archive به مسیر نهایی:

```text
bench press dumbell.gif -> upper-body/chest/dumbbell-bench-press.gif
bent row.gif -> upper-body/back/barbell-bent-over-row.gif
elevations-laterales-exercice-musculation-700.gif -> upper-body/shoulders/dumbbell-lateral-raise.gif
Bent-Over-Lateral-Raise.gif -> upper-body/shoulders/rear-delt-fly.gif
Smith-Machine-Shoulder-Press.gif -> upper-body/shoulders/smith-machine-shoulder-press.gif
cable-curl123.gif -> upper-body/biceps/cable-curl.gif
جلو-بازو-هالتر-ایستاده.gif -> upper-body/biceps/barbell-curl.gif
جلو-بازو-دمبل-ایستاده-تک-تک.gif -> upper-body/biceps/dumbbell-curl.gif
hammer curl.gif -> upper-body/biceps/hammer-curl.gif
Seated-Dumbbell-Triceps-Extension12.gif -> upper-body/triceps/overhead-dumbbell-extension.gif
تمرین-پل-باسن-هالتر-1.gif -> lower-body/glutes/glute-bridge.gif
goblet squat.gif -> lower-body/quadriceps/goblet-squat.gif
تمرین-پرس-پا.gif -> lower-body/quadriceps/leg-press.gif
تمرین-جلو-پا-ماشین.gif -> lower-body/quadriceps/leg-extension.gif
تمرین-دمبل-لانچ.gif -> lower-body/quadriceps/dumbbell-lunge.gif
تمرین-ددلیفت-رومانیایی.gif -> lower-body/hamstrings/romanian-deadlift.gif
تمرین-ساق-پا-ایستاده.gif -> lower-body/calves/standing-calf-raise.gif
```

این ۱۷ رکورد `media_type` برابر `gif`، `media_license` برابر
`Project owner supplied and authorized` و `media_attribution` برابر
`Provided by Fitsho project owner` دارند. چون دارایی محلی مالک پروژه هستند،
`media_source_url` آن‌ها `NULL` است. نام فایل اصلی archive در سند attribution ثبت
می‌شود.

هیچ رکورد placeholder در seed ساخته نمی‌شود. مدل، API و frontend همچنان placeholder
اصلی فیتشو با مسیر زیر را برای رکوردهای آینده بدون رسانه پشتیبانی می‌کنند:

```text
/exercises/exercise-placeholder.svg
```

فایل‌ها در ساختار ناحیه و عضله نگهداری می‌شوند. فایل خارجی آینده فقط از پنل مدیریت
مستقل و با منبع، سازنده، مجوز و attribution روشن پذیرفته خواهد شد.
`docs/exercise-media-attribution.md` مسیر نهایی، نام فایل archive، ارائه‌دهنده و مجوز
هر ۱۷ دارایی را ثبت می‌کند.

ساختار فعلی نقطه توسعه پنل ادمین آینده است: ادمین می‌تواند یک `slug` یکتا، نام‌های
دوزبانه، ناحیه، عضله اصلی، عضلات فرعی، تجهیزات، سطح، مراحل اجرا، نکات ایمنی و رسانه
را ثبت کند. فایل آپلودشده در filesystem ذخیره و فقط مسیر و metadata آن در PostgreSQL
قرار می‌گیرد. این feature هیچ endpoint نوشتنی یا صفحه ادمین ایجاد نمی‌کند.

## ۶. API و کنترل دسترسی

```text
GET /api/v1/exercise-categories
GET /api/v1/exercises
GET /api/v1/exercises/{slug}
```

هر سه endpoint به session معتبر و `user_profiles` موجود نیاز دارند:

```text
401: session معتبر نیست
403: پروفایل تکمیل نشده است
404: slug وجود ندارد یا غیرفعال است
422: مقدار فیلتر یا صفحه‌بندی نامعتبر است
503: دیتابیس موقتاً در دسترس نیست
```

فهرست فقط `is_active = true` را برمی‌گرداند و این فیلترها را می‌پذیرد:

```text
body_region
primary_muscle
equipment
difficulty
search
page
page_size
```

`page` از ۱ شروع می‌شود و `page_size` محدود است. پاسخ شامل items، page، page_size،
total و total_pages است. category endpoint ترتیب ثابت ناحیه‌ها و عضلات و برچسب
فارسی و انگلیسی آن‌ها را برمی‌گرداند. دسته‌ها از taxonomy کنترل‌شده ساخته می‌شوند،
نه از رکوردهای موجود؛ بنابراین `abs`، `obliques` و `lower_back` حتی با صفر حرکت نیز
نمایش داده می‌شوند و برای افزودن آینده از پنل ادمین آماده‌اند.

## ۷. frontend

ساختار دامنه:

```text
frontend/src/features/exercises/
├── api.ts
├── types.ts
├── ExerciseCatalogPage.tsx
├── ExerciseDetailPage.tsx
├── ExerciseMedia.tsx
└── exercises.css
```

مسیرهای زیر داخل `ProtectedRoute` و `CompletedProfileRoute` فعلی ثبت می‌شوند:

```text
/exercises
/exercises/:slug
```

انتخاب ناحیه، عضله، تجهیزات، سطح، جست‌وجو و صفحه در query string نگهداری می‌شود.
این کار back/forward مرورگر، لینک قابل اشتراک و تغییر مستقیم فیلتر را بدون state
سراسری جدید فراهم می‌کند.

صفحه catalog سه بخش پیوسته دارد:

1. انتخاب ناحیه بدن
2. انتخاب گروه عضلانی همان ناحیه
3. فیلترها و grid کارت‌های responsive

breadcrumb مسیر انتخاب را نمایش می‌دهد، ولی کنترل‌های ناحیه و عضله همیشه قابل تغییر
هستند. هر کارت رسانه واقعی یا placeholder، هر دو نام با اولویت زبان فعال، عضله اصلی،
تجهیزات، سطح و لینک جزئیات دارد.

صفحه detail هر دو نام، media، عضلات اصلی و فرعی، تجهیزات، سطح، مراحل شماره‌دار،
نکات ایمنی و بازگشت به catalog را نمایش می‌دهد. عناصر فارسی `dir="rtl"` و عناصر
انگلیسی `dir="ltr"` مناسب دارند.

حالت‌های زیر مستقل نمایش و تست می‌شوند:

- loading
- خطای API و retry
- نتیجه خالی و فیلتر بدون نتیجه
- slug ناشناخته
- media غایب یا خراب
- placeholder

header یک لینک Exercises کنار Dashboard و Profile می‌گیرد و dashboard یک کارت
مستقیم به catalog اضافه می‌کند. CSS از tokenها، focus state، breakpointها،
`prefers-reduced-motion` و الگوهای موجود استفاده می‌کند.

## ۸. تست و راستی‌آزمایی

backend:

- constraintها، slug یکتا و مقادیر دسته‌بندی معتبر/نامعتبر
- فهرست، جزئیات، همه فیلترها، جست‌وجو و صفحه‌بندی
- مخفی‌بودن رکورد غیرفعال و slug ناشناخته
- نیاز به authentication و profile
- idempotency کامل seed
- upgrade و downgrade migration

frontend:

- route protection
- navigation از header و dashboard
- انتخاب ناحیه و عضله
- کارت‌ها، فیلترها و جزئیات
- loading، error، retry و empty
- نام‌های فارسی و انگلیسی و RTL/LTR
- ۱۷ رسانه مالک پروژه، دسته‌های خالی، fallback placeholder و خرابی media

فرمان‌های نهایی:

```text
docker compose up -d db
backend/.venv/bin/alembic upgrade head
backend/.venv/bin/pytest
backend/.venv/bin/ruff check app tests
backend/.venv/bin/ruff format --check app tests
backend/.venv/bin/mypy app tests
npm test
npm run lint
npm run build
git diff --check
```

## ۹. مستندات تحویلی

- معماری catalog و تصمیم‌های رابطه‌ای
- دستور seed و رفتار idempotent
- ساختار پوشه‌های media
- شرایط مجوز و attribution
- روش امن افزودن حرکت جدید
- الزام ارجاع برنامه‌های آینده به `exercises.id`
- `docs/exercise-media-attribution.md`

پس از عبور همه بررسی‌ها، کل قابلیت با یک commit زیر ثبت می‌شود:

```text
feat(exercises): add browsable exercise catalog
```
