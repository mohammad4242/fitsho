# معماری و عملیات پنل مدیریت تمرین

## محدوده و مجوز دسترسی

پنل مدیریت فقط برای افزودن تمرین به کاتالوگ موجود است. ویرایش، حذف، مدیریت حرکت
جایگزین و API عمومی نوشتن در این قابلیت وجود ندارد.

ستون `users.is_admin` با مقدار پیش‌فرض پایگاه داده `false` مجوز مدیر را نگه می‌دارد.
ثبت‌نام عمومی این فیلد را نمی‌پذیرد. پاسخ `/api/v1/auth/me` فقط همین وضعیت بولی را
برای تصمیم‌گیری رابط کاربری برمی‌گرداند. کنترل سمت سرور مرجع نهایی است:

- مهمان: `401`
- کاربر واردشده غیرمدیر: `403`
- مدیر: مجاز، حتی بدون پروفایل ورزشی کامل

برای ارتقای امن و تکرارپذیر یک کاربر موجود، از `backend/` اجرا کن:

```bash
.venv/bin/python -m app.admin.grant_admin admin@example.com
```

دستور حساب جدید نمی‌سازد و اگر ایمیل وجود نداشته باشد با خطای روشن متوقف می‌شود.

## APIهای مدیریت

```text
GET  /api/v1/admin/exercises
POST /api/v1/admin/exercises
```

لیست مدیریت فعال و غیرفعال را برمی‌گرداند و پارامترهای `search`، `is_active`،
`page` و `page_size` را می‌پذیرد. ایجاد تمرین با `multipart/form-data` انجام می‌شود:

- بخش `payload`: یک رشته JSON شامل داده‌های زیر
- بخش اختیاری `media`: یک فایل GIF، MP4 یا WebM

فیلدهای `payload`:

```text
slug                 required, lowercase kebab-case, unique
name_en              required
name_fa              required
body_region          required enum
primary_muscle       required enum
secondary_muscles    array of enums; may be empty
equipment            non-empty array of enums; bodyweight is valid
difficulty           required enum
instructions_en      ordered array, 3–6 non-empty steps
instructions_fa      ordered array, 3–6 non-empty steps
safety_notes_en      non-empty ordered array
safety_notes_fa      non-empty ordered array
is_active            boolean, default true
media_source_url     optional
media_license        optional
media_attribution    optional
```

`id`، زمان‌ها، نام فایل ذخیره‌شده، `media_path` و `media_type` توسط سرور تولید
می‌شوند. عضله اصلی و فرعی باید به ناحیه بدن انتخاب‌شده تعلق داشته باشند. تجهیزات و
عضلات فرعی در جدول‌های association نرمال‌شده ذخیره می‌شوند. تمرین فعال بلافاصله در
کاتالوگ عمومی دیده می‌شود؛ تمرین غیرفعال فقط در لیست مدیریت قابل مشاهده است.

ایجاد موفق `201`، slug تکراری `409` و داده نامعتبر `422` برمی‌گرداند. mutation از
همان کنترل trusted-origin/CSRF نشست فعلی استفاده می‌کند.

## ذخیره و امنیت رسانه

مسیر runtime پیش‌فرض `backend/var/media` و Git-ignored است. فایل در
`frontend/public` یا PostgreSQL نوشته نمی‌شود؛ پایگاه داده فقط مسیر عمومی و metadata
را نگه می‌دارد. نبود فایل از placeholder موجود استفاده می‌کند.

اعتبارسنجی آپلود شامل این موارد است:

- allowlist هم‌زمان پسوند و MIME برای GIF، MP4 و WebM
- تطبیق signature واقعی فایل با پسوند
- رد فایل خالی، نام دارای separator/path traversal و نوع اجرایی یا دلخواه
- سقف پیش‌فرض ۲۰ MiB (`MEDIA_MAX_BYTES=20971520`)
- سقف پیش‌فرض ویدیو ۲۰ ثانیه (`MEDIA_MAX_VIDEO_DURATION_SECONDS=20`)
- تشخیص مدت با `ffprobe` بدون shell و با timeout
- نام UUID تصادفی سمت سرور و انتشار exclusive؛ فایل موجود overwrite نمی‌شود
- حذف فایل تازه‌نوشته‌شده در صورت شکست transaction پایگاه داده

`MEDIA_ROOT`، `MEDIA_PUBLIC_PATH`، محدودیت حجم، محدودیت مدت، `FFPROBE_PATH` و
`FFPROBE_TIMEOUT_SECONDS` قابل تنظیم‌اند. اگر فایل متعلق به مالک پروژه باشد و metadata
وارد نشود، مجوز و attribution امن مالک پروژه به‌طور پیش‌فرض ثبت می‌شود. پیش‌نمایش
ویدیو در پنل کنترل دارد و با صدا autoplay نمی‌شود.

## Docker، پایداری و پشتیبان‌گیری

سرویس backend در Compose، `ffprobe` را داخل image دارد. رسانه‌ها در volume نام‌دار
`fitsho_exercise_media` زیر `/var/lib/fitsho/media` می‌مانند. حذف container فایل‌ها را
حذف نمی‌کند، اما حذف volume آن‌ها را از بین می‌برد.

پشتیبان عملیاتی باید PostgreSQL و volume رسانه را در یک نقطه زمانی هماهنگ نگه دارد.
بازیابی فقط یکی از آن‌ها می‌تواند رکورد بدون فایل یا فایل بدون رکورد بسازد. پیش از
upgrade، migration یا جابه‌جایی محیط، از هر دو نسخه پشتیبان بگیر و بازیابی هر دو را
آزمایش کن. runtime uploadها نباید در Git یا image build کپی شوند.

## همزیستی seed و داده مدیر

`python -m app.exercises.seed` فقط slugهای متعلق به manifest seed را update می‌کند.
تمرین ساخته‌شده توسط مدیر به seed تبدیل، حذف یا بازنویسی نمی‌شود و UUID، associationها
و `media_path` آن ثابت می‌ماند. فایل رسانه سفارشی نیز توسط seed لمس نمی‌شود.

برنامه‌های تمرینی آینده باید با foreign key به `exercises.id` اشاره کنند؛ slug، نام یا
متن تمرین کلید رابطه نیست.

## مسیرهای رابط کاربری

```text
/admin/exercises
/admin/exercises/new
```

لینک مدیریت فقط برای مدیر نمایش داده می‌شود و `AdminRoute` دسترسی مستقیم مهمان و
غیرمدیر را نیز می‌بندد. فرم دوزبانه با RTL/LTR، پیشنهاد slug قابل‌ویرایش، کنترل‌های
چندانتخابی، فیلدهای تکرارشونده، پیش‌نمایش رسانه، placeholder، وضعیت ارسال و retry از
قراردادهای فعلی فیتشو استفاده می‌کند. چون API client فعلی Fetch درصد پیشرفت upload
نمی‌دهد، رابط وضعیت بارگذاری نامعین و واقعی نمایش می‌دهد.
