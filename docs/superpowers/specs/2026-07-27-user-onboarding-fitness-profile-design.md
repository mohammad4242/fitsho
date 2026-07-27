# طراحی onboarding کاربر و پروفایل ورزشی فیتشو

تاریخ: ۱۴۰۵/۰۵/۰۵

## ۱. هدف

این قابلیت پس از احراز هویت، اطلاعات اولیه لازم برای شناخت وضعیت ورزشی کاربر را
دریافت و نگهداری می‌کند. هر کاربر فقط یک پروفایل پایدار دارد، اما وزن او به‌صورت
رکوردهای جداگانه ذخیره می‌شود تا تاریخچه وزن بدون بازنویسی داده‌های قبلی قابل توسعه
باشد.

کاربری که session معتبر دارد ولی هنوز پروفایل نساخته است باید به مسیر
`/onboarding` هدایت شود. کاربر دارای پروفایل می‌تواند dashboard و صفحه مشاهده و
ویرایش پروفایل را ببیند.

## ۲. محدوده

موارد داخل این مرحله:

- onboarding سه‌مرحله‌ای پس از ثبت‌نام یا ورود
- نام نمایشی، تاریخ تولد، جنس، قد، وزن فعلی، هدف ورزشی، سطح تجربه، تعداد روز تمرین
  هفتگی و محدودیت‌های جسمی اختیاری
- جدول one-to-one برای اطلاعات پایدار پروفایل
- جدول جداگانه و append-only برای وزن
- API ساخت، خواندن و ویرایش پروفایل
- route protection برای مهمان، کاربر بدون پروفایل و کاربر دارای پروفایل
- رابط مشاهده و ویرایش پروفایل
- validation هماهنگ در frontend و backend و constraintهای مناسب دیتابیس
- migrationهای Alembic
- تست‌های backend و frontend با ابزارهای موجود پروژه
- رابط دو‌زبانه فارسی و انگلیسی هماهنگ با authentication موجود

موارد خارج از این مرحله:

- تولید برنامه تمرینی
- برنامه‌ریزی تغذیه
- قابلیت‌های AI
- نمودار پیشرفت یا صفحه تاریخچه measurementها
- Redis، cache، queue یا background worker
- ذخیره draft ناقص onboarding
- تست مرورگر با Playwright
- مدل‌سازی ساخت‌یافته آسیب، درد، ناحیه بدن یا شدت محدودیت

## ۳. گزینه‌های معماری بررسی‌شده

### ۳.۱. ماژول مستقل profile و درخواست مستقل وضعیت پروفایل

اجزا:

```text
AuthContext
ProfileProvider
ProfileRouteGuard
/api/v1/profile
user_profiles
body_measurements
```

پس از مشخص‌شدن session، frontend پروفایل را مستقل دریافت می‌کند. پاسخ موفق به معنی
تکمیل onboarding و پاسخ `404` به معنی نیاز به onboarding است.

مزایا:

- مرز روشن میان هویت حساب و اطلاعات ورزشی
- تست‌پذیری مستقل auth و profile
- توسعه measurementها بدون تغییر قرارداد authentication
- هماهنگی با modular monolith فعلی

معایب:

- یک درخواست اضافه پس از بررسی session
- نیاز به حالت loading و خطای مستقل برای profile

پیچیدگی: متوسط

بهترین کاربرد: برنامه API-first با قابلیت‌های دامنه‌ای رو به رشد.

### ۳.۲. افزودن `has_profile` به پاسخ authentication

پاسخ register، login و `GET /auth/me` علاوه بر user، وضعیت وجود profile را برمی‌گرداند.

مزایا:

- یک درخواست کمتر هنگام شروع frontend
- تصمیم سریع‌تر route guard پس از احراز هویت

معایب:

- وابستگی مستقیم auth به جدول profile
- نیاز به همگام‌سازی AuthContext پس از ساخت profile
- رشد تدریجی قرارداد auth با جزئیات دامنه‌های دیگر

پیچیدگی: کم در ابتدا و پرهزینه‌تر در زمان رشد.

بهترین کاربرد: محصول بسیار کوچک که profile فقط extension ساده user است.

### ۳.۳. endpoint تجمیعی bootstrap

یک endpoint مانند `GET /api/v1/bootstrap` اطلاعات user، profile و وضعیت onboarding را
در یک پاسخ برمی‌گرداند.

مزایا:

- یک درخواست startup برای frontend
- امکان افزودن داده‌های dashboard در آینده

معایب:

- coupling زودهنگام auth، profile و dashboard
- قرارداد مرکزی بزرگ و دشوارتر برای versioning و caching
- پیچیدگی بیشتر از نیاز فعلی

پیچیدگی: متوسط تا زیاد

بهترین کاربرد: برنامه بالغی که startup آن واقعاً به چند منبع داده وابسته است.

## ۴. تصمیم معماری

گزینه نخست انتخاب شد. profile یک ماژول مستقل در همان FastAPI modular monolith است و
frontend وضعیت آن را جدا از authentication نگهداری می‌کند.

جریان startup:

```text
Browser
  -> GET /api/v1/auth/me
  -> authenticated user
  -> GET /api/v1/profile
  -> 404: /onboarding
  -> 200: /dashboard
  -> network/database error: retry state
```

فقط `404` به معنی profile ناقص است. خطای ارتباط یا دیتابیس نباید باعث redirect اشتباه
به onboarding شود.

## ۵. مدل داده

### ۵.۱. جدول `user_profiles`

```text
user_id                 UUID, PK, FK -> users.id, ON DELETE CASCADE
display_name            VARCHAR(80), NOT NULL
birth_date              DATE, NOT NULL
sex                     VARCHAR, NOT NULL, CHECK
height_cm                SMALLINT, NOT NULL, CHECK
fitness_goal             VARCHAR, NOT NULL, CHECK
experience_level         VARCHAR, NOT NULL, CHECK
training_days_per_week   SMALLINT, NOT NULL, CHECK
physical_limitations     TEXT, NULL, CHECK length <= 1000
created_at               TIMESTAMPTZ, NOT NULL
updated_at               TIMESTAMPTZ, NOT NULL
```

استفاده از `user_id` به‌عنوان primary key و foreign key هم‌زمان، رابطه one-to-one را
بدون شناسه اضافی یا unique constraint دوم تضمین می‌کند.

### ۵.۲. جدول `body_measurements`

```text
id             UUID, PK
user_id        UUID, FK -> users.id, ON DELETE CASCADE
weight_kg      NUMERIC(5,2), NOT NULL, CHECK
measured_at    TIMESTAMPTZ, NOT NULL
```

روی `(user_id, measured_at)` index ساخته می‌شود تا آخرین وزن هر کاربر به‌صورت مؤثر
خوانده شود. `NUMERIC` به‌جای `FLOAT` انتخاب شده است تا وزن اعشاری بدون خطای نمایش
دودویی ذخیره شود.

وزن append-only است. ساخت profile اولین measurement را می‌سازد و تغییر وزن از مسیر
ویرایش پروفایل رکورد جدید اضافه می‌کند. هیچ measurement قبلی overwrite نمی‌شود.

### ۵.۳. enumها

```text
sex:
  female
  male
  other
  prefer_not_to_say

fitness_goal:
  lose_weight
  build_muscle
  improve_fitness
  maintain_weight

experience_level:
  beginner
  intermediate
  advanced
```

enumها با `VARCHAR` و `CHECK constraint` ذخیره می‌شوند. PostgreSQL native enum کنترل
قوی دارد ولی تغییر گزینه‌ها را دشوارتر می‌کند. lookup table برای مقادیری مناسب‌تر
است که در زمان اجرا توسط مدیر تغییر می‌کنند و برای این گزینه‌های ثابت پیچیدگی اضافه
دارد.

### ۵.۴. محدوده validation

```text
display_name:             2 تا 80 کاراکتر پس از trim
birth_date:               سن کامل بین 18 تا 100 سال
height_cm:                100 تا 250 سانتی‌متر
weight_kg:                20 تا 500 کیلوگرم، حداکثر دو رقم اعشار
training_days_per_week:   1 تا 7
physical_limitations:     اختیاری، حداکثر 1000 کاراکتر
```

فاصله ابتدا و انتهای نام نمایشی و متن محدودیت حذف می‌شود. متن محدودیت خالی پس از
trim به `NULL` تبدیل می‌شود. constraintهای مستقل از زمان در دیتابیس و تمام قواعد در
Pydantic و frontend اعمال می‌شوند. شرط سنی به دلیل وابستگی به تاریخ روز در لایه
application بررسی می‌شود.

## ۶. قرارداد API

هر endpoint به session معتبر نیاز دارد. `user_id` از session استخراج می‌شود و در
path یا request body پذیرفته نمی‌شود.

### ۶.۱. ساخت profile

```text
POST /api/v1/profile
```

نمونه request:

```json
{
  "display_name": "Mohammad",
  "birth_date": "2000-05-14",
  "sex": "male",
  "height_cm": 178,
  "current_weight_kg": 76.5,
  "fitness_goal": "build_muscle",
  "experience_level": "beginner",
  "training_days_per_week": 3,
  "physical_limitations": null
}
```

سرویس `user_profiles` و اولین `body_measurements` را در یک transaction می‌سازد.
موفقیت `201 Created` و profile تکراری `409 Conflict` برمی‌گرداند. شکست هر insert باعث
rollback کامل هر دو می‌شود.

### ۶.۲. خواندن profile

```text
GET /api/v1/profile
```

پاسخ شامل اطلاعات پایدار و آخرین وزن مشتق‌شده است:

```json
{
  "user_id": "00000000-0000-0000-0000-000000000000",
  "display_name": "Mohammad",
  "birth_date": "2000-05-14",
  "sex": "male",
  "height_cm": 178,
  "current_weight_kg": 76.5,
  "weight_measured_at": "2026-07-27T10:30:00Z",
  "fitness_goal": "build_muscle",
  "experience_level": "beginner",
  "training_days_per_week": 3,
  "physical_limitations": null,
  "created_at": "2026-07-27T10:30:00Z",
  "updated_at": "2026-07-27T10:30:00Z"
}
```

نبودن profile پاسخ `404 Not Found` دارد.

### ۶.۳. ویرایش profile

```text
PATCH /api/v1/profile
```

فقط فیلدهای ارسال‌شده تغییر می‌کنند. body خالی `422 Unprocessable Content` است. اگر
وزن ارسالی با آخرین وزن متفاوت باشد measurement جدید ساخته می‌شود؛ ارسال دوباره
همان وزن رکورد تکراری نمی‌سازد. profile غایب پاسخ `404` دارد.

تغییر profile و افزودن measurement احتمالی در یک transaction انجام می‌شوند. ردیف
profile با `SELECT ... FOR UPDATE` قفل می‌شود تا updateهای هم‌زمان یک کاربر serialize
شوند و measurement تکراری ناشی از race condition ساخته نشود.

### ۶.۴. پاسخ‌های خطا

```text
401  session معتبر نیست
404  profile وجود ندارد
409  profile قبلاً ساخته شده است
422  request نامعتبر است
503  database موقتاً در دسترس نیست
```

`POST` و `PATCH` همان trusted-Origin protection موجود را دارند. method `PATCH` به
CORS اضافه می‌شود. جزئیات حساس مانند محدودیت جسمی در log یا پاسخ خطا قرار نمی‌گیرد.

endpoint مستقلی برای تاریخچه measurement در این مرحله ساخته نمی‌شود.

## ۷. ساختار backend

```text
backend/app/profile/
├── __init__.py
├── models.py
├── schemas.py
├── exceptions.py
├── service.py
└── router.py
```

مرزها:

- router فقط HTTP، dependencyها و نگاشت خطا را مدیریت می‌کند.
- schemas قرارداد عمومی و validation را تعریف می‌کنند.
- service مالک use caseها و transactionها است.
- models فقط نگاشت جداول و constraintها را نگه می‌دارد.
- exceptions خطاهای domain را از HTTP مستقل می‌کنند.

repository layer جدا اضافه نمی‌شود؛ `SQLAlchemy Session` برای اندازه فعلی قابلیت مرز
کافی است.

migration جدید:

```text
backend/alembic/versions/20260727_02_create_fitness_profiles.py
down_revision = "20260724_01"
```

migration ابتدا `user_profiles`، سپس `body_measurements` و index آخرین measurement را
می‌سازد. downgrade ترتیب معکوس دارد و migration هیچ داده نمونه وارد نمی‌کند.

## ۸. ساختار frontend و route protection

ساختار مفهومی:

```text
frontend/src/features/profile/
├── types.ts
├── api.ts
├── ProfileContext.tsx
├── profileValidation.ts
├── ProfileRouteGuards.tsx
├── OnboardingPage.tsx
└── ProfilePage.tsx
```

`ProfileProvider` وضعیت‌های زیر را صریح نگه می‌دارد:

```text
idle
loading
missing
ready
error
```

provider فقط پس از وجود user احراز هویت‌شده درخواست profile را اجرا می‌کند و پس از
logout وضعیت خود را reset می‌کند.

رفتار routeها:

| وضعیت | `/login` و `/register` | `/onboarding` | `/dashboard` و `/profile` |
|---|---|---|---|
| مهمان | مجاز | انتقال به `/login` | انتقال به `/login` |
| واردشده بدون profile | انتقال به `/onboarding` | مجاز | انتقال به `/onboarding` |
| واردشده دارای profile | انتقال به `/dashboard` | انتقال به `/dashboard` | مجاز |
| خطای profile | نمایش خطا و retry | نمایش خطا و retry | نمایش خطا و retry |

## ۹. تجربه onboarding و ویرایش

فرم onboarding سه مرحله دارد:

```text
1. display name, birth date, sex
2. height, current weight, fitness goal
3. experience level, training days, physical limitations
```

هر مرحله پیش از ادامه validate می‌شود. Back داده‌های حافظه فرم را حفظ می‌کند. refresh
یا بستن صفحه draft را حذف می‌کند؛ اطلاعات سلامتی در `localStorage` ذخیره نمی‌شوند.
submit فقط در مرحله آخر انجام می‌شود و پس از موفقیت ProfileContext با پاسخ API
به‌روزرسانی و کاربر به `/dashboard` منتقل می‌شود.

خطای API روی فرم نمایش داده می‌شود و ورودی‌ها حفظ می‌شوند. خطاهای field کنار input
مرتبط نمایش داده شده و focus به اولین field نامعتبر منتقل می‌شود. progress مراحل برای
screen reader قابل تشخیص است.

صفحه `/profile` اطلاعات را می‌خواند و همه فیلدها، از جمله وزن فعلی، را با `PATCH`
ویرایش می‌کند. dashboard لینک واضحی به این صفحه دارد. تمام labelها، hintها و خطاها در
منابع i18n فارسی و انگلیسی تعریف می‌شوند.

## ۱۰. validation frontend و انتخاب dependency

dependency تازه‌ای برای فرم اضافه نمی‌شود. قواعد در یک ماژول pure قرار می‌گیرند و
inputها نیز از `required`، `min`، `max` و `maxLength` استفاده می‌کنند.

دلیل انتخاب:

- ۹ فیلد ثابت با state محلی و تابع validation قابل مدیریت است.
- توابع pure مستقیماً unit test می‌شوند.
- abstraction و dependency غیرضروری به پروژه اضافه نمی‌شود.

جایگزین‌ها:

- `React Hook Form` برای فرم‌های بزرگ، پویا یا دارای field array مناسب‌تر است.
- `Zod` برای schemaهای پیچیده و استفاده مشترک چند فرم ارزش بیشتری دارد.
- ترکیب `React Hook Form` و `Zod` قدرتمند است، ولی برای scope فعلی dependency و لایه
  انتزاعی اضافه ایجاد می‌کند و validation backend را نیز حذف نمی‌کند.

## ۱۱. راهبرد تست

تست backend روی PostgreSQL واقعی اجرا می‌شود.

پوشش backend:

- constraintهای دیتابیس، رابطه one-to-one، foreign key و cascade
- ساخت atomic پروفایل و measurement و rollback هنگام شکست
- authentication الزامی برای هر endpoint
- پاسخ‌های `201`، `401`، `404`، `409`، `422` و `503`
- دریافت آخرین وزن
- ویرایش فیلدهای پایدار
- افزودن measurement برای وزن جدید و نساختن رکورد برای وزن یکسان
- جداسازی داده دو user
- مرزهای دقیق سن، قد، وزن، روز تمرین و طول متن

پوشش frontend:

- قرارداد fetch و `credentials: include`
- تفاوت profile غایب با خطای شبکه
- transitionهای ProfileContext
- ماتریس redirect مسیرها
- validation تمام boundaryها
- حرکت سه‌مرحله‌ای، Back و حفظ state
- submit نهایی و نمایش خطای API
- نمایش و ویرایش profile
- رفتار retry هنگام خطای startup

ابزارهای موجود حفظ می‌شوند:

```text
backend: pytest, Ruff, mypy
frontend: Vitest, React Testing Library, oxlint, TypeScript/Vite build
database: Alembic upgrade and downgrade verification
```

`Playwright` در این مرحله اضافه نمی‌شود. تست‌های backend و frontend مسیر کامل قابلیت
را در مرزهای خود پوشش می‌دهند، اما ادعای تست مرورگر واقعی ندارند.

## ۱۲. معیار پذیرش

- ثبت‌نام یا ورود کاربر بدون profile نهایتاً او را به `/onboarding` می‌برد.
- کاربر مهمان نمی‌تواند onboarding، dashboard یا profile را ببیند.
- کاربر دارای profile نمی‌تواند onboarding را دوباره به‌عنوان create flow باز کند.
- ساخت profile دقیقاً یک `user_profiles` و یک measurement اولیه می‌سازد.
- تغییر وزن تاریخچه را حفظ می‌کند.
- frontend و backend داده نامعتبر را رد می‌کنند.
- خطای شبکه باعث redirect اشتباه نمی‌شود و retry قابل استفاده است.
- migration upgrade و downgrade موفق‌اند.
- تمام تست‌های authentication و profile، lint، type check و build موفق‌اند.
- هیچ قابلیت workout، nutrition، AI، chart یا Redis اضافه نمی‌شود.
