# معماری و عملیات کاتالوگ حرکات

## محدوده

کاتالوگ یک ماژول مستقل و فقط‌خواندنی برای کاربران عادی است. کاربر باید وارد حساب شده
باشد و پروفایل ورزشی کامل داشته باشد. این ماژول برنامه تمرینی، هوش مصنوعی، ثبت ست یا
پنل مدیریت را پیاده‌سازی نمی‌کند.

مرزهای اصلی:

- `backend/app/exercises/`: مدل‌ها، enumها، schemaها، queryها، routeها و seed.
- `frontend/src/features/exercises/`: قرارداد API، مرور کاتالوگ، جزئیات و نمایش رسانه.
- `frontend/public/exercises/`: فایل‌های رسانه محلی؛ هیچ فایل باینری در PostgreSQL نیست.
- `docs/exercise-media-attribution.md`: منبع و مجوز تمام رسانه‌های committed.

سه API فقط‌خواندنی ارائه می‌شوند:

- `GET /api/v1/exercise-categories`
- `GET /api/v1/exercises`
- `GET /api/v1/exercises/{slug}`

هر سه route از `require_completed_profile` استفاده می‌کنند. رکوردهای `is_active=false`
در list و detail نمایش داده نمی‌شوند.

## طراحی داده و trade-off

چهار جدول ساخته شده است:

1. `exercises`: هویت پایدار، نام‌های دوزبانه، دسته‌بندی، متن اجرا، نکات ایمنی و metadata رسانه.
2. `exercise_secondary_muscles`: رابطه چندمقداری و قابل جستجو برای عضلات فرعی.
3. `exercise_equipment`: رابطه چندمقداری و قابل جستجو برای تجهیزات.
4. `exercise_alternatives`: جایگزین‌های صریح و curated همراه دلیل فارسی و انگلیسی.

عضلات فرعی و تجهیزات در جدول‌های association نرمال شده‌اند؛ چون collectionهای مهم و
قابل query هستند. مراحل اجرا و نکات ایمنی به‌صورت آرایه JSON داخل `exercises` نگه‌داری
می‌شوند؛ ترتیب آن‌ها مهم است ولی در این feature روی اعضای داخلی آن‌ها query نداریم.

جایگزین‌ها صریح هستند، نه خودکار. اشتراک عضله اصلی به‌تنهایی به‌معنای جایگزین امن نیست.
در آینده می‌توان از فیلدهای ساخت‌یافته برای پیشنهادهای پویا استفاده کرد، اما نتیجه باید
curated و تأییدشده باشد.

برنامه‌های تمرینی آینده باید با foreign key به `exercises.id` متصل شوند؛ نام حرکت، slug یا
متن تولیدشده توسط AI کلید رابطه نیست.

## مقادیر کنترل‌شده

```text
body_region:
  upper_body, lower_body, core

primary/secondary muscle:
  chest, back, shoulders, biceps, triceps, traps,
  glutes, quadriceps, hamstrings, adductors, calves,
  abs, obliques, lower_back

equipment:
  bodyweight, dumbbell, barbell, cable, machine,
  resistance_band, bench, pull_up_bar, other

difficulty:
  beginner, intermediate, advanced

media_type:
  image, animated_webp, gif, video, placeholder
```

افزودن مقدار جدید به این مجموعه‌ها تغییر schema است و باید enum پایتون، TypeScript،
ترجمه‌ها، migration و تست‌ها با هم به‌روزرسانی شوند.

## محدودیت‌های مهم مدل

- `slug` یکتا، پایدار و فقط شامل حروف کوچک انگلیسی، عدد و خط تیره است.
- نام فارسی و انگلیسی بین ۲ تا ۱۶۰ نویسه دارند.
- دستورهای هر زبان ۳ تا ۶ مرحله هستند.
- هر زبان حداقل یک نکته ایمنی دارد.
- یک حرکت نمی‌تواند جایگزین خودش باشد.
- حذف exercise با `ON DELETE CASCADE` associationهای آن را پاک می‌کند.

## migration و راه‌اندازی

ترتیب migrationها:

```text
20260724_01  authentication
20260727_02  fitness profiles
20260727_03  exercise catalog
```

از `backend/` اجرا کن:

```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m app.exercises.seed
```

Seed بعد از migration اجرا می‌شود و بخشی از startup برنامه نیست.

## رفتار seed

منبع seed در `backend/app/exercises/seed_data.py` است. برای هر slug، شناسه UUIDv5 با
namespace ثابت `https://fitsho.local/exercises/` ساخته می‌شود. بنابراین اجرای مجدد seed
همان `exercises.id` را حفظ می‌کند.

Seed یک upsert idempotent است:

- فیلدهای scalar رکوردهای seedشده را به مقدار source-of-truth برمی‌گرداند.
- رکورد seedشده را فعال می‌کند.
- عضلات فرعی و تجهیزات را با مجموعه seed همگام می‌کند؛ عضو حذف‌شده واقعاً از association
  حذف و عضو جدید اضافه می‌شود.
- جایگزین‌های تعریف‌شده را بر اساس دو شناسه upsert می‌کند.
- exerciseهای خارج از seed را حذف نمی‌کند.
- همه تغییرها در یک transaction commit می‌شوند و خطا باعث rollback می‌شود.

خروجی فعلی:

```text
Seeded 17 exercises and 1 alternative.
```

تنها رابطه جایگزین فعلی `leg-press -> goblet-squat` است. این رابطه یک‌طرفه است و صرفاً
به‌دلیل نبود دستگاه پرس پا تعریف شده؛ reverse یا سایر حرکات هم‌عضله خودکار ساخته نمی‌شوند.

## فیلتر و صفحه‌بندی

`GET /api/v1/exercises` این query parameterها را می‌پذیرد:

```text
body_region
primary_muscle
equipment
difficulty
search
page       (default: 1)
page_size  (default: 12, maximum: 50)
```

فیلتر equipment از association table و `EXISTS` استفاده می‌کند. جستجو روی نام فارسی،
نام انگلیسی و slug انجام می‌شود و wildcardهای SQL escape می‌شوند. پاسخ شامل `total` و
`total_pages` است. مقدار نامعتبر enum یا pagination با پاسخ `422` رد می‌شود.

## افزودن امن یک حرکت seedشده

1. facts حرکت، مراحل اجرا و نکات ایمنی را از منبع معتبر بررسی کن؛ محتوا درمان پزشکی نیست.
2. یک slug پایدار انتخاب کن. تغییر slug یعنی هویت seed جدید و شناسه جدید.
3. برای رسانه، ابتدا مراحل `docs/exercise-media-attribution.md` را انجام بده.
4. فایل را در پوشه درست `frontend/public/exercises/` با نام slug قرار بده.
5. برای رسانه مالک پروژه، path و `MediaType` را به `_OWNER_MEDIA` اضافه کن. برای رسانه
   خارجی دارای مجوز، seed را گسترش بده تا `media_source_url`، `media_license` و
   `media_attribution` همان asset را ثبت کند؛ metadata مالک پروژه را reuse نکن.
6. یک `ExerciseSeed` دوزبانه با ۳ تا ۶ مرحله و حداقل یک نکته ایمنی برای هر زبان اضافه کن.
7. عضلات فرعی و تجهیزات را با enumها ثبت کن؛ رشته comma-separated ذخیره نکن.
8. اگر جایگزین واقعاً هم‌الگو و ایمن است، یک `AlternativeSeed` با دلیل دوزبانه اضافه کن.
9. migration، seed و تست‌ها را اجرا کن و سپس list/detail را در هر دو زبان بررسی کن.

برای حرکت بدون رسانه مجاز، از این مقادیر استفاده کن:

```text
media_path: /exercises/exercise-placeholder.svg
media_type: placeholder
```

## نکته برای پنل مدیریت آینده

پنل مدیریت باید همین constraints، associationها و metadata مجوز را اعمال کند. آپلود فایل
در storage محلی انجام می‌شود و فقط `media_path` در PostgreSQL ذخیره می‌شود. API عمومی
create/update/delete در این feature وجود ندارد.
