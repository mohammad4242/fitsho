# Fitsho Exercise Media Consolidation & Safe Migration

## ماموریت

ریپوی **Fitsho** و محیط لوکال فعلی آن را بررسی کن و سیستم ویدیوهای حرکات را به یک ساختار **واحد، مرتب، قابل‌انتقال به سرور و بدون از دست رفتن حتی یک فایل** منتقل کن.

این یک کار حساس روی فایل‌ها و دیتابیس است.  
**هیچ ویدیویی، فایل مدیا، رکورد مدیا یا Volume قدیمی نباید حذف شود.**

تو برای این کار اختیار کامل داری که:

- پوشه جدید بسازی.
- فایل‌ها را Rename کنی.
- فایل‌ها را Copy کنی.
- ساختار پوشه‌ها را تغییر بدهی.
- Docker Compose و Media Mountها را اصلاح کنی.
- مسیرهای دیتابیس را Migration/Update کنی.
- کد Backend/Frontend مرتبط با Media را اصلاح کنی.
- اسکریپت Migration و Audit بنویسی.
- تست اضافه کنی.

اما **حق حذف فایل اصلی، Volume قدیمی یا رکوردی که حاوی مدیاست را نداری.**

---

# زمینه مشکل فعلی

بررسی قبلی نشان داده است که Media حرکات در چند محل و چند مدل مختلف پخش شده:

- `Exercise.media_path`
- `Exercise.media_type`
- `ExerciseMediaAsset`
- `exercise_media_assets`
- ویدیوهای male/female/unspecified
- فایل‌های Free Exercise DB
- فایل‌های owner-video
- فایل‌های آپلودشده توسط Admin
- Docker Named Volume
- Bind Mountهای مختلف

همچنین مشخص شده:

1. بعضی ویدیوها در `media_assets` وجود دارند ولی `Exercise.media_path` هنوز `placeholder.svg` است.
2. کارت کاتالوگ و صفحه جزئیات حرکت از منطق یکسانی برای انتخاب Media استفاده نمی‌کنند.
3. بعضی حرکات دارای رکورد Placeholder تکراری هستند، در حالی که رکورد دیگری از همان حرکت ویدیو دارد.
4. Seed یا Importer در بعضی شرایط ممکن است Media را دوباره overwrite کند.
5. بررسی قبلی نشان داده فایل‌های ویدیویی فعلی روی دیسک هنوز موجودند.

این موارد را **فرض قطعی نکن**؛ قبل از تغییر، وضعیت فعلی Repository، Database، Docker volumes و فایل‌های واقعی را دوباره بررسی و تأیید کن.

---

# هدف نهایی

در پایان باید فقط **یک Media Root اصلی و قابل‌انتقال** برای تمام ویدیوهای حرکات داشته باشیم.

پیشنهاد اصلی:

```text
backend/var/media/
└── exercises/
    ├── <exercise-folder>/
    │   ├── video-01.mp4
    │   ├── video-02.mp4
    │   └── ...
    └── ...
```

می‌توانی در صورت وجود دلیل فنی بهتر، نام‌گذاری پوشه را تغییر بدهی.

مثلاً:

```text
<slug>--<short-id>
```

یا هر ساختار deterministic و بدون collision دیگری.

شرط‌ها:

- هر فایل باید دقیقاً قابل ردیابی باشد که متعلق به کدام `exercise_id` است.
- Extension واقعی فایل حفظ شود.
- نام فایل‌ها deterministic و collision-safe باشد.
- مسیرها مستقل از نام دستگاه لوکال باشند.
- کل Media Root بعداً بتواند با یک `rsync/scp` به سرور منتقل شود.
- Backend نباید به مسیر absolute مخصوص لپ‌تاپ وابسته باشد.

---

# قانون شماره ۱ — هیچ فایل اصلی حذف نشود

در Migration اولیه:

**COPY کن، MOVE نکن.**

حتی اگر از نظر فنی Move ممکن است، فایل‌های منبع فعلی را دست‌نخورده نگه دار.

نباید از موارد زیر استفاده شود:

```text
rm
rm -rf
unlink
docker volume rm
docker compose down -v
docker system prune --volumes
shutil.move
os.remove
Path.unlink
```

همچنین:

- Named Volume فعلی را حذف نکن.
- فایل‌های owner-video را حذف نکن.
- فایل‌های free-exercise-db را حذف نکن.
- فایل‌های Admin upload را حذف نکن.
- فایل‌های Bind Mount قدیمی را حذف نکن.

در پایان این Task، نسخه قدیمی باید همچنان به عنوان Safety Backup وجود داشته باشد.

---

# Phase 1 — Inventory کامل قبل از هر تغییر

قبل از تغییر کد یا فایل، یک Inventory کامل تهیه کن.

تمام منابع Media را پیدا کن:

### Database

بررسی کن:

```text
Exercise.media_path
Exercise.media_type
Exercise.media_source_url
Exercise.source
Exercise.source_id

ExerciseMediaAsset.exercise_id
ExerciseMediaAsset.media_path
ExerciseMediaAsset.media_type
ExerciseMediaAsset.presentation
ExerciseMediaAsset.role
ExerciseMediaAsset.sort_order
```

### Filesystem / Docker

تمام مسیرهای واقعی را بررسی کن، از جمله:

```text
MEDIA_ROOT
Docker named volumes
fitsho_exercise_media
owner-video
free-exercise-db
meal-catalogue
admin uploads
bind mounts
```

و Compose فعلی را دقیق بخوان.

---

# Phase 2 — ساخت Manifest

قبل از کپی فایل‌ها یک Manifest بساز.

برای هر فایل Media حداقل این اطلاعات را ثبت کن:

```text
exercise_id
exercise_slug
exercise_name_fa
exercise_name_en
source
source_id

current_db_path
current_physical_path

media_asset_id
presentation
role
sort_order
media_type

file_size
sha256

destination_relative_path
destination_physical_path

exists_before
copied
hash_verified
db_updated
```

Manifest را در یک مسیر امن مثل زیر ذخیره کن:

```text
backend/var/media-migration/
    before_inventory.json
    before_inventory.csv
    migration_manifest.json
```

این فایل‌ها را commit نکن اگر شامل داده Runtime هستند؛ در صورت نیاز `.gitignore` را اصلاح کن.

---

# Phase 3 — تشخیص فایل‌های Duplicate و Broken

قبل از Migration مشخص کن:

### A

رکوردهایی که:

```text
media_path = placeholder
```

دارند ولی `media_assets` معتبر دارند.

### B

رکوردهایی که DB به فایل اشاره می‌کند ولی فایل واقعاً وجود ندارد.

### C

فایل‌هایی که روی دیسک وجود دارند ولی هیچ DB reference ندارند.

### D

فایل‌هایی که SHA256 یکسان دارند ولی با نام یا مسیر متفاوت ذخیره شده‌اند.

### E

حرکت‌هایی که چند رکورد Database ظاهراً معادل دارند، مانند مواردی از جنس:

```text
machine-chest-press
pec-deck-fly
lying-leg-curl
romanian-deadlift
```

در مورد Duplicate Exerciseها **حدس نزن**.

فقط زمانی دو رکورد را معادل بدان که شواهد کافی مثل موارد زیر وجود داشته باشد:

- slug/name
- muscle/equipment
- source/source_id
- template references
- instructions
- media
- programming metadata

اگر معادل بودن قطعی نیست، رکوردها را جدا نگه دار و فقط گزارش کن.

---

# Phase 4 — ساخت Media Storage واحد

یک Media Root واحد روی Host ایجاد کن.

هدف ترجیحی:

```text
backend/var/media/exercises/
```

تمام ویدیوهای حرکات از تمام منابع فعلی باید به این Media Root **کپی** شوند.

برای هر فایل:

1. وجود Source را چک کن.
2. SHA256 بگیر.
3. Destination path بساز.
4. با metadata مناسب Copy کن.
5. SHA256 فایل مقصد را دوباره بگیر.
6. Source و Destination hash باید دقیقاً برابر باشند.
7. فقط بعد از تأیید Hash اجازه داری DB path را تغییر بدهی.

استفاده از `shutil.copy2` یا روش امن مشابه مناسب است.

---

# Phase 5 — نام‌گذاری فایل‌ها

یک Naming convention تمیز و deterministic ایجاد کن.

مثلاً:

```text
backend/var/media/exercises/<slug>--<short-id>/
    male-01.mp4
    male-02.mp4
    female-01.mp4
    unspecified-01.mp4
```

یا اگر role مهم است:

```text
male-video-01.mp4
female-video-01.mp4
unspecified-video-01.mp4
```

اگر collision رخ داد، از hash کوتاه استفاده کن:

```text
male-video-01-a3f912cd.mp4
```

نام‌گذاری باید:

- deterministic
- human-readable
- collision-safe
- server-friendly

باشد.

---

# Phase 6 — تغییر Docker Compose

هدف این است که دیگر ویدیوهای حرکات بین چند Volume و Bind Mount پراکنده نباشند.

در صورت سازگاری با معماری پروژه، Compose را به یک Mount اصلی تبدیل کن، مثلاً:

```yaml
- ./backend/var/media:/var/lib/fitsho/media
```

و:

```text
MEDIA_ROOT=/var/lib/fitsho/media
```

را حفظ یا استاندارد کن.

اما:

**قبل از تغییر Mount حتماً تمام داده موجود در Named Volume فعلی را به Host Media Root جدید Copy و Verify کن.**

Named Volume قدیمی را بعد از Migration حذف نکن.

بعد از تغییر Compose، برنامه باید فقط از Media Root جدید استفاده کند.

---

# Phase 7 — Database Migration

بعد از اینکه Copy و Hash verification موفق شد، DB را به مسیرهای جدید اشاره بده.

تمام Media pathها باید relative/public باشند و به ماشین خاص وابسته نباشند.

مثلاً:

```text
/media/exercises/<exercise-folder>/male-01.mp4
```

نه:

```text
/home/mohammad/...
```

و نه مسیر مستقیم Docker Volume.

Database update باید Transactional باشد.

اگر بخشی از Migration fail شد:

- transaction rollback شود.
- فایل‌های اصلی دست‌نخورده بمانند.
- فایل‌های Copy شده نیز برای Debug باقی بمانند.

---

# Phase 8 — Single Source of Truth برای نمایش Media

مشکل دوگانگی فعلی را اصلاح کن.

Backend و Frontend باید یک منطق مشترک داشته باشند:

اول:

```text
ExerciseMediaAsset
```

و اگر Asset معتبر وجود نداشت:

```text
legacy Exercise.media_path
```

به عنوان fallback.

اگر `media_path` برابر placeholder باشد ولی یک `media_asset` معتبر وجود داشته باشد، UI باید ویدیو را نمایش دهد.

یک helper/resolver واحد بساز تا:

- Exercise Catalog
- Exercise Detail
- Admin Preview
- Workout display

همگی از یک منطق Media استفاده کنند.

منطق انتخاب ویدیو در چند فایل کپی نشود.

---

# Phase 9 — Legacy media_path

فعلاً `Exercise.media_path` را ناگهانی حذف نکن.

برای Backward Compatibility:

- `media_assets` را Source of Truth اصلی قرار بده.
- `media_path` را fallback یا primary preview compatibility نگه دار.
- در صورت نیاز برای رکوردهای موجود آن را از Asset معتبر Sync کن.

اما معماری جدید نباید برای نمایش صحیح صرفاً به `media_path` وابسته باشد.

---

# Phase 10 — Admin Upload

Admin upload را اصلاح کن تا تمام ویدیوهای جدید مستقیماً داخل Media Root واحد ذخیره شوند.

مثلاً:

```text
/media/exercises/<exercise-folder>/...
```

اضافه شدن Media Asset جدید باید:

- Asset را صحیح ذخیره کند.
- primary preview را در صورت نیاز sync کند.
- هیچ Asset قبلی را بدون درخواست صریح حذف نکند.

ویرایش Exercise بدون Upload جدید نیز نباید Media قبلی را از بین ببرد.

---

# Phase 11 — Seed و Importer Protection

تمام Seedها و Importerها را بررسی کن، خصوصاً:

```text
seed_exercises
_apply_seed_fields
free_exercise_db_import
_apply_candidate
_sync_media_assets
owner_video_import
```

قانون:

**Media دستی Admin نباید توسط Seed یا Importer overwrite شود.**

اگر لازم است Media ownership/provenance مشخص شود، آن را با معماری تمیز پیاده‌سازی کن.

مثلاً تفاوت بین:

```text
admin
seed
free-exercise-db
owner-video
```

باید قابل تشخیص باشد.

Seed باید برای initialize کردن Media مناسب باشد، نه برای خراب کردن انتخاب Admin.

---

# Phase 12 — Placeholder / Duplicate Exercises

Duplicate Placeholderها را کامل Audit کن.

اگر یک Placeholder Exercise و یک Exercise معتبر ویدیودار واقعاً یک حرکت هستند:

- ابتدا تمام referenceها را پیدا کن.
- Training Templates را بررسی کن.
- FKها را بررسی کن.
- Workout references را بررسی کن.
- Mediaها را بررسی کن.

در این Task هیچ Exercise record را hard-delete نکن.

اگر consolidation کاملاً امن است، referenceها را به رکورد canonical منتقل کن.

در غیر این صورت فقط mapping/report تهیه کن و رفتار UI را طوری اصلاح کن که رکورد اشتباه نمایش داده نشود.

---

# Phase 13 — Verification اجباری

بعد از Migration یک Audit خودکار اجرا کن.

باید ثابت شود:

### File verification

```text
TOTAL_SOURCE_FILES
TOTAL_DESTINATION_FILES
TOTAL_DISTINCT_SHA256
MISSING_SOURCE_FILES
HASH_MISMATCHES
BROKEN_DB_PATHS
ORPHAN_DESTINATION_FILES
```

مقدارهای زیر باید صفر باشند:

```text
HASH_MISMATCHES = 0
BROKEN_DB_PATHS = 0
```

هر فایل referenced در DB باید روی Media Root جدید وجود داشته باشد.

---

# Phase 14 — Functional Test

برنامه را بالا بیاور و حداقل این موارد را تست کن:

- Exercise Catalog
- Exercise Detail
- male/female media switch
- Admin Exercise Edit
- Admin Media Upload
- Training program exercise display

حرکت‌های شناخته‌شده مشکل‌دار را حتماً دستی/اتوماتیک تست کن:

```text
Romanian Deadlift
Machine Chest Press
Pec Deck Fly
Lying Leg Curl
Barbell Hip Thrust
Dumbbell Squat
```

---

# Phase 15 — Automated Tests

برای رفتار جدید تست اضافه کن.

حداقل:

1. Catalog از `media_assets` استفاده می‌کند.
2. Placeholder legacy path باعث پنهان شدن Asset معتبر نمی‌شود.
3. Detail و Catalog یک primary media را انتخاب می‌کنند.
4. Admin edit بدون media upload فایل قبلی را حفظ می‌کند.
5. Seed، Admin media را overwrite نمی‌کند.
6. Importer، Admin media را overwrite نمی‌کند.
7. Media paths جدید قابل resolve هستند.
8. Migration script در اجرای دوباره Idempotent است.

---

# Phase 16 — Idempotency

Migration script باید بتواند چند بار اجرا شود بدون اینکه:

- فایل duplicate بی‌دلیل بسازد.
- pathها خراب شوند.
- Assetها دو بار ایجاد شوند.
- داده overwrite اشتباه شود.

اگر Destination file با SHA256 درست از قبل وجود دارد:

```text
SKIP + VERIFY
```

انجام بده.

---

# Phase 17 — Rollback

یک Rollback plan واقعی بنویس.

چون فایل‌های قدیمی حذف نمی‌شوند، Rollback باید بتواند:

- Database paths قبلی را از Manifest برگرداند.
- Compose mount قدیمی را restore کند.
- بدون از دست رفتن فایل انجام شود.

Rollback را تست کن یا حداقل Dry Run معتبر داشته باش.

---

# Phase 18 — انتقال آینده به Server

بعد از این Refactor، انتقال Media به Server باید ساده باشد.

هدف این است که بعداً تقریباً فقط این پوشه منتقل شود:

```text
backend/var/media/
```

مثلاً با:

```text
rsync
```

و Backend روی Server همان ساختار `/media/...` را ببیند.

هیچ path مخصوص لپ‌تاپ نباید داخل Database ذخیره شود.

---

# ممنوعیت‌های قطعی

تا پایان این Task:

- هیچ فایل Media را Delete نکن.
- هیچ Docker Volume را Delete نکن.
- هیچ Exercise یا Media Asset را Hard Delete نکن.
- `docker compose down -v` اجرا نکن.
- `docker volume rm` اجرا نکن.
- `prune --volumes` اجرا نکن.
- برای تشخیص Duplicateها صرفاً بر اساس اسم حدس نزن.
- Migration را بدون Backup/Manifest اجرا نکن.
- قبل از Hash Verification مسیر DB را تغییر نده.
- اگر وضعیت مبهم بود، روش محافظه‌کارانه را انتخاب کن.

---

# اختیار اجرا

برای انجام این Migration لازم نیست برای Rename، ساخت Folder، Copy، تغییر Compose، ایجاد Migration script، تغییر کد یا اجرای Test از من اجازه بگیری.

در چهارچوب قوانین بالا کار را کامل انجام بده.

تنها چیزی که اجازه نداری انجام بدهی **حذف داده یا فایل اصلی** است.

---

# خروجی نهایی

پس از اتمام، پاسخ نهایی را **به فارسی** بده و دقیقاً این موارد را گزارش کن:

## 1. وضعیت قبل

- چند فایل ویدیویی پیدا شد؟
- در چند محل مختلف بودند؟
- چند Exercise دارای Media بود؟
- چند Broken reference وجود داشت؟
- چند Placeholder/duplicate پیدا شد؟

## 2. چه تغییراتی انجام شد؟

خلاصه فایل‌های کد، Migrationها، Compose و Storage structure.

## 3. Media Root جدید

مسیر دقیق را اعلام کن.

## 4. نتیجه انتقال

مثلاً:

```text
Source files: X
Copied files: X
Verified hashes: X
Hash mismatches: 0
Broken DB references: 0
Deleted files: 0
```

## 5. حرکت‌های مشکل‌دار

وضعیت نهایی:

```text
Romanian Deadlift
Machine Chest Press
Pec Deck Fly
Lying Leg Curl
Barbell Hip Thrust
Dumbbell Squat
```

## 6. Duplicate records

بگو کدام‌ها پیدا شدند و با آنها چه کردی.

## 7. Seed / Importer

بگو چگونه جلوی overwrite شدن Admin media گرفته شد.

## 8. Docker

بگو Media الان دقیقاً چگونه Mount می‌شود و چرا با rebuild/restart از بین نمی‌رود.

## 9. Tests

نتیجه تست‌ها را با command و نتیجه واقعی اعلام کن.

## 10. Safety confirmation

در آخر صریحاً اعلام کن:

```text
هیچ فایل ویدیویی حذف نشده است.
هیچ Volume قدیمی حذف نشده است.
تمام فایل‌های منتقل‌شده با hash بررسی شده‌اند.
Media Root جدید برای انتقال آینده به Server آماده است.
```

---

# اصل نهایی

اول **Inventory**  
بعد **Copy**  
بعد **Hash Verify**  
بعد **Database Update**  
بعد **Application Test**

هرگز ترتیب بالا را برعکس نکن.
