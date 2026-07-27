# رسانه‌های کاتالوگ حرکات

## سیاست رسانه

رسانه باید به‌صورت فایل محلی زیر `frontend/public/exercises/` نگه‌داری شود. hotlink،
scraping یا دانلود تصادفی از YouTube، Instagram، TikTok، اپلیکیشن‌های تجاری، سایت‌های
نامشخص و نتایج جستجوی تصویر مجاز نیست.

برای هر فایل خارجی، پیش از commit باید این اطلاعات تأیید و ثبت شوند:

- URL مستقیم صفحه منبع، نه URL موتور جستجو.
- نام سازنده یا عبارت صریح `unknown/not supplied`؛ سازنده را حدس نزن.
- مجوز روشن: Public Domain، CC0، CC BY یا CC BY-SA.
- متن attribution موردنیاز مجوز.
- رعایت ShareAlike برای CC BY-SA.

اگر مالکیت یا مجوز روشن نیست، فایل اضافه نمی‌شود و
`/exercises/exercise-placeholder.svg` استفاده می‌شود. مقدارهای `media_source_url`،
`media_license` و `media_attribution` باید با همین registry هماهنگ باشند.

فایل‌های فعلی GIF توسط مالک پروژه برای انتشار در همین repository ارائه و مجاز شده‌اند.
URL منبع و نام سازنده اصلی همراه archive ارائه نشده است؛ بنابراین در registry جعل نشده و
به‌صراحت `not supplied` ثبت شده است. رکوردهای فعلی seed نیز
`media_source_url = null` دارند.

## ساختار پوشه

```text
frontend/public/exercises/
├── exercise-placeholder.svg
├── upper-body/
│   ├── chest/
│   ├── back/
│   ├── shoulders/
│   ├── biceps/
│   ├── triceps/
│   └── traps/
├── lower-body/
│   ├── glutes/
│   ├── quadriceps/
│   ├── hamstrings/
│   ├── adductors/
│   └── calves/
└── core/
    ├── abs/
    ├── obliques/
    └── lower-back/
```

پوشه‌های خالی برای دسته‌هایی هستند که بعداً از مسیر مدیریت امن تکمیل می‌شوند.

## رجیستری attribution

| مسیر نهایی | نام فایل اصلی | فراهم‌کننده | سازنده | منبع | مجوز | attribution |
|---|---|---|---|---|---|---|
| `frontend/public/exercises/exercise-placeholder.svg` | `exercise-placeholder.svg` | Fitsho | Fitsho | local | project-owned | not required |
| `frontend/public/exercises/upper-body/chest/dumbbell-bench-press.gif` | `bench press dumbell.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/back/barbell-bent-over-row.gif` | `bent row.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/shoulders/dumbbell-lateral-raise.gif` | `elevations-laterales-exercice-musculation-700.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/shoulders/rear-delt-fly.gif` | `Bent-Over-Lateral-Raise.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/shoulders/smith-machine-shoulder-press.gif` | `Smith-Machine-Shoulder-Press.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/biceps/cable-curl.gif` | `cable-curl123.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/biceps/barbell-curl.gif` | `جلو-بازو-هالتر-ایستاده.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/biceps/dumbbell-curl.gif` | `جلو-بازو-دمبل-ایستاده-تک-تک.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/biceps/hammer-curl.gif` | `hammer curl.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/upper-body/triceps/overhead-dumbbell-extension.gif` | `Seated-Dumbbell-Triceps-Extension12.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/glutes/glute-bridge.gif` | `تمرین-پل-باسن-هالتر-1.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/quadriceps/goblet-squat.gif` | `goblet squat.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/quadriceps/leg-press.gif` | `تمرین-پرس-پا.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/quadriceps/leg-extension.gif` | `تمرین-جلو-پا-ماشین.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/quadriceps/dumbbell-lunge.gif` | `تمرین-دمبل-لانچ.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/hamstrings/romanian-deadlift.gif` | `تمرین-ددلیفت-رومانیایی.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |
| `frontend/public/exercises/lower-body/calves/standing-calf-raise.gif` | `تمرین-ساق-پا-ایستاده.gif` | Fitsho project owner | not supplied | owner-provided local archive | Project owner supplied and authorized | Provided by Fitsho project owner |

## افزودن رسانه جدید

1. مجوز را از صفحه اصلی منبع بخوان و screenshot یا متن شرایط را برای review نگه دار.
2. در صورت نیاز، attribution دقیق سازنده را آماده کن.
3. فایل را دانلود و محلی کن؛ URL خارجی در UI استفاده نکن.
4. نام فایل را با slug هماهنگ و در دسته درست قرار بده.
5. یک ردیف به registry بالا اضافه کن.
6. `media_source_url`، `media_license` و `media_attribution` رکورد را تکمیل کن.
7. برای تصویر alt مناسب و برای ویدیو controls، `muted` و `playsInline` را حفظ کن؛ صدا
   خودکار پخش نشود.
