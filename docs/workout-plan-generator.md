# مولد برنامه تمرینی شخصی

این قابلیت برای کاربر دارای پروفایل کامل، یک برنامه هفتگی مقاومت/قدرت می‌سازد و آن را
برای دوره انتخابی ۴، ۶ یا ۸ هفته‌ای نگه می‌دارد. برنامه فقط با حرکت‌های واجد شرایط
کاتالوگ فیتشو ساخته می‌شود؛ React هرگز مستقیماً با سرویس AI ارتباط نمی‌گیرد.

## معماری

`backend/app/workouts` مالک انتخاب حرکت، امضای تولید، سیاست زمان، اعتبارسنجی، ذخیره‌سازی
و فعال‌سازی اتمیک است. `backend/app/ai` فقط قرارداد provider، adapter مربوط به OpenCode
Zen و provider جعلی تست‌ها را نگه می‌دارد.

روند تولید:

1. backend پروفایل کامل، حرکت فعال فعلی و کاندیدهای مجاز را می‌خواند.
2. اگر امضای برنامه فعال برابر باشد و دوره آن تمام نشده باشد، همان برنامه با `reused=true`
   بازمی‌گردد.
3. در غیر این صورت یک رکورد generation کوتاه‌مدت ساخته و commit می‌شود.
4. درخواست ساخت‌یافته بدون transaction باز به Zen ارسال می‌شود.
5. پاسخ Pydantic و سپس قوانین معنایی backend را می‌گذراند. فقط در این نقطه برنامه جدید
   ذخیره، برنامه قبلی supersede و برنامه جدید active می‌شود.

اگر provider، parsing، اعتبارسنجی یا ذخیره‌سازی شکست بخورد، generation ناموفق ثبت می‌شود و
برنامه فعال قبلی دست‌نخورده باقی می‌ماند. در هر کاربر تنها یک generation در حال اجرا مجاز است.

## کاتالوگ و انتخاب حرکت

حرکت قابل تولید باید هم `is_active=true` و هم `is_programmable=true` باشد. metadata لازم:

- `movement_pattern`
- `exercise_type`
- `caution_tags`
- `is_programmable`

مدیر می‌تواند این فیلدها را هنگام افزودن یا ویرایش حرکت تعیین کند. بنابراین افزودن یا حذف
حرکت در آینده، بدون تغییر prompt یا کد، مجموعه کاندیدهای تولید بعدی را تغییر می‌دهد.

selector همه تجهیزات موردنیاز حرکت را با تجهیزات کاربر مقایسه می‌کند (`required ⊆ available`).
bodyweight-only فقط bodyweight، خانه با دمبل فقط bodyweight و dumbbell، و gym تجهیزات پشتیبانی‌شده
باشگاه را دارد. سطح تجربه و cautionهای ساخت‌یافته نیز پیش از فراخوانی مدل اعمال می‌شوند.

## امضا، stale و دوره برنامه

امضا یک SHA-256 از JSON canonical است و شامل هدف، بازه وزن ۵kg، تجربه، روزهای تمرین، محل و
تجهیزات، زمان جلسه، دوره برنامه، cautionها، محدودیت متنی sanitised، hash کاندیدها، نسخه کاتالوگ،
مدل، prompt و policy است. نام نمایشی، ایمیل، شناسه کاربر، سن، قد، تاریخ تولد و داده نشست در آن نیست.

برنامه active اگر امضایش عوض شود یا از `activated_at + plan_duration_weeks × 7 days` بگذرد stale
است. stale بودن برنامه را حذف نمی‌کند؛ کاربر همچنان آن را می‌بیند و با Generate برنامه بعدی را
می‌سازد. تغییر نام نمایشی، سن یا قد به‌تنهایی stale نمی‌کند.

## OpenCode Zen و provider

تنها adapter تولیدی فعلی `OpenCodeZenWorkoutPlanProvider` است. برای مدل‌های GPT 5.6 از Responses
API با JSON Schema strict، `store=false` و `httpx.AsyncClient` مشترک استفاده می‌کند؛ برای
`nemotron-3-ultra-free` از OpenAI-compatible Chat Completions استفاده می‌کند. provider دیگری مانند
Gemini باید adapter جداگانه‌ای بسازد که `WorkoutPlanModelProvider` را پیاده‌سازی کند؛ service تغییر
نمی‌کند.

یادداشت عملیاتی: مدل‌های GPT 5.6 از Responses API استفاده می‌کنند؛
`nemotron-3-ultra-free` از OpenAI-compatible Chat Completions استفاده می‌کند. مدل ناشناخته همچنان
به Responses API بازمی‌گردد.

متغیرهای backend:

```text
OPENCODE_ZEN_API_KEY=
OPENCODE_ZEN_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_ZEN_MODEL=gpt-5.6-terra
OPENCODE_ZEN_TIMEOUT_SECONDS=30
OPENCODE_ZEN_PROXY_URL=
WORKOUT_PROMPT_VERSION=v1
WORKOUT_POLICY_VERSION=v1
WORKOUT_CATALOG_PROGRAMMING_VERSION=v1
WORKOUT_MAX_REPAIR_ATTEMPTS=1
WORKOUT_GENERATION_COOLDOWN_SECONDS=300
WORKOUT_MAX_CANDIDATES=80
WORKOUT_MAX_REQUEST_BYTES=262144
WORKOUT_WARMUP_MINUTES=5
```

کلید فقط در محیط backend قرار می‌گیرد. آن را در `.env` محلی نگه دار، هرگز در frontend یا Git
قرار نده. timeout، خطاهای شبکه، 401/403، 429، 5xx، پاسخ غیر JSON و schema نامعتبر به خطای عمومی
و امن برای کاربر تبدیل می‌شوند.

## Prompt، خروجی و repair

system prompt نسخه‌دار در `prompt_builder.py` قرار دارد. متن محدودیت فیزیکی کاربر پیش از ارسال
sanitize و به‌عنوان داده JSON جدا از دستور سیستم قرار می‌گیرد؛ هیچ دستور داخل آن قابل اجرا نیست.
فقط کمینه داده لازم (سن محاسبه‌شده، جنسیت در صورت وجود، قد، وزن، هدف، تجربه، برنامه، تجهیز، زمان و
caution) به provider می‌رود؛ نام، ایمیل، تاریخ تولد، توکن و cookie هرگز ارسال نمی‌شوند.

مدل فقط `exercise_id`های candidateهای ارسالی و schema دقیق روزها/حرکت‌ها را برمی‌گرداند. validator
backend روزها، شناسه‌ها، وضعیت فعلی کاتالوگ، تجهیز، caution، تجربه، تکرار، ست، استراحت، RIR، زمان،
توازن و تکرارهای ناخواسته را بررسی می‌کند. در پاسخ نامعتبر، حداکثر یک repair با همان candidateها و
فهرست خطاها اجرا می‌شود؛ candidate جدیدی اضافه نمی‌شود.

## حریم خصوصی و لاگ

generation record فقط metadata عملیاتی امن مانند provider، model، زمان، token count و safe error
message را نگه می‌دارد. API key، cookie، ایمیل، تاریخ تولد دقیق، prompt خام حساس و پاسخ خام حساس
ذخیره یا serialize نمی‌شوند. در زمان نگارش، [سیاست Zen](https://opencode.ai/docs/zen/) برای providerها
zero-retention را با استثناهای وابسته به مدل اعلام می‌کند و برای OpenAI APIها نگه‌داری ۳۰روزه را ذکر
می‌کند؛ پیش از انتخاب مدل، سیاست جاری همان مدل را دوباره بررسی کن. این قابلیت ایمنی بالینی یا
اعتبارسنجی حرفه‌ای را ادعا نمی‌کند و تشخیص یا درمان پزشکی نیست.

## API و رابط کاربری

- `GET /api/v1/workout-plans/active` برنامه active را بدون تماس AI برمی‌گرداند و `is_stale` را مشخص
  می‌کند.
- `POST /api/v1/workout-plans/generate` برنامه reusable را برمی‌گرداند یا برنامه جدید می‌سازد.
- `GET /api/v1/workout-plans/{plan_id}` فقط برای مالک برنامه قابل خواندن است.

مسیر محافظت‌شده `/workout-plan` راهنمای ثابت، برنامه کامل با media کاتالوگ و لینک جزئیات حرکت را
نمایش می‌دهد. کارت‌های PDF خلاصه فارسی، بازخورد پایان دوره و تحلیل عکس بدن فعلاً placeholder هستند؛
در این قابلیت tracking، feedback ذخیره‌شده، آپلود عکس، PDF واقعی یا chat پیاده‌سازی نشده است.

## اجرای تست‌ها

تمام تست‌های عادی از `FakeWorkoutPlanModelProvider` یا transport جعلی استفاده می‌کنند و هرگز Zen را
صدا نمی‌زنند:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest
.venv/bin/ruff check app tests alembic
.venv/bin/ruff format --check app tests alembic
.venv/bin/mypy app tests

cd ../frontend
npm test
npm run lint
npm run build
```

تست زنده فقط با اجازه صریح و داده مصنوعی اجرا می‌شود:

```bash
cd backend
ZEN_LIVE_TEST=true OPENCODE_ZEN_API_KEY=... .venv/bin/pytest tests/ai/test_zen_live.py -q
```

این دستور هزینه provider دارد و بخشی از CI نیست. اگر سرور backend دسترسی مستقیم به Zen ندارد،
نشانی proxy را فقط در متغیر backend به‌صورت `OPENCODE_ZEN_PROXY_URL` تنظیم کن؛ برای نمونه
`socks5://127.0.0.1:10808`. این proxy فقط برای client مربوط به Zen استفاده می‌شود و frontend
هرگز به آن یا کلید API دسترسی ندارد.
