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

## بازبینی برنامه توسط مربی

بعد از فعال‌شدن هر برنامهٔ تولیدشده، همان نسخه برای کاربر قابل اجرا می‌ماند و یک بازبینی با وضعیت
`pending` ساخته می‌شود. کاربر پیام «در انتظار تأیید مربی» را می‌بیند؛ انتظار برای مربی برنامهٔ فعال
را از دسترس خارج نمی‌کند.

مربی دارای role دقیق `coach` از مسیر `/coach/workouts` صف مشترک را می‌بیند. claim یک lease سی‌دقیقه‌ای
ایجاد می‌کند و در هر لحظه فقط همان مربی می‌تواند draft را ویرایش یا تأیید کند. تمدید lease، ذخیرهٔ draft
و approval همگی revision و مالکیت claim را کنترل می‌کنند.

تأیید، برنامهٔ اولیه را ویرایش نمی‌کند. یک `WorkoutPlan` مستقل از snapshot تأییدشده ساخته و فعال می‌شود
و نسخهٔ اولیه به تاریخچه می‌رود. کاربر از صفحهٔ برنامه می‌تواند هر دو نسخه را فقط برای مشاهده باز کند؛
تنها نسخهٔ فعال قابلیت ساخت نسخهٔ بعدی را دارد.

APIهای عضو:

```text
GET /api/v1/workout-plans/active
GET /api/v1/workout-plans/history
GET /api/v1/workout-plans/{plan_id}
```

APIهای مربی زیر `/api/v1/coach/workout-reviews` هستند و بدون `coach` role پاسخ 403 می‌دهند. اعطای role
با همان جدول موجود `user_specialist_roles` انجام می‌شود؛ admin بودن به‌تنهایی دسترسی مربی ایجاد نمی‌کند.
در محیط عملیاتی role باید فقط از ابزار مدیریت دسترسی داده شود. نمونهٔ SQL توسعه:

```sql
INSERT INTO user_specialist_roles (user_id, role)
SELECT id, 'coach' FROM users WHERE email = 'coach@example.com'
ON CONFLICT DO NOTHING;
```

مهاجرت مربوط به این قابلیت `20260809_58` است و جدول `workout_plan_reviews` را اضافه می‌کند. برنامه‌های
قدیمی بدون بازبینی معتبر می‌مانند و برای آن‌ها review ساختگی ایجاد نمی‌شود.
