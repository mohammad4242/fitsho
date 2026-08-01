# مولد برنامهٔ تمرینی Fitsho

تصمیم‌های برنامه از نسخهٔ V1 به‌صورت deterministic داخل backend گرفته می‌شوند. هیچ LLM یا provider
خارجی split، exercise، volume، ترتیب، prescription، progression یا اعتبار برنامه را تعیین نمی‌کند.

مسیر اصلی:

```text
POST /api/v1/workout-plans/generate
WorkoutGenerationService
app/workouts/program_engine
validator مستقل
ذخیره و فعال‌سازی اتمیک
```

API قبلی و فیلدهای مصرفی frontend حفظ شده‌اند. body درخواست اختیاری است و می‌تواند شواهدی را که
هنوز در profile اصلی ذخیره نشده‌اند—مثل training age، recovery، priority muscles، محدودیت‌های
قابل‌محاسبه و seed—به‌صورت typed دریافت کند.

اگر ورودی red flag یا محدودیت مبهم داشته باشد، پاسخ 422 با کد ساخت‌یافته می‌آید و برنامه‌ای ذخیره
نمی‌شود. اگر حرکت امن برای pattern ضروری وجود نداشته باشد نیز engine حرکت ناامن جایگزین نمی‌کند.

هر برنامهٔ جدید موارد زیر را snapshot می‌کند:

- normalized profile
- engine/ruleset version و seed
- catalog hash و metadata حرکات مرتبط
- prescription، cardio و progression
- assumptions، warnings، validation report و decision trace
- ارتباط نسخهٔ قبلی و difference summary هنگام regeneration

بنابراین ویرایش بعدی catalog خروجی تاریخی را تغییر نمی‌دهد. برنامهٔ قبلی فقط وقتی supersede می‌شود
که برنامهٔ جدید بدون validation error در همان transaction فعال شود.

مستندات تفصیلی:

- `docs/program-engine-architecture.md`
- `docs/program-engine-rules.md`
- `docs/program-engine-science-basis.md`
- `docs/program-engine-migration.md`
- `docs/program-engine-examples.md`

دستورهای بررسی:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test .venv/bin/pytest -q
.venv/bin/ruff check
.venv/bin/mypy app
DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:55433/fitsho_test .venv/bin/alembic check

cd ../frontend
npm run test
npm run lint
npm run build
```

تست زندهٔ Zen همچنان فقط برای diagnostics بخش AI و با opt-in صریح موجود است؛ مسیر workout
generation آن را فراخوانی نمی‌کند.
