# اجرای محلی فیتشو

## درگاه‌ها

```text
Frontend: http://localhost:5173
Backend API: http://localhost:8000
API documentation: http://localhost:8000/docs
PostgreSQL: localhost:5432
```

## پیش‌نیازها

```text
Python 3.12+
Node.js 24+
uv
Docker with Docker Compose
```

## ۱. پایگاه داده

از ریشه پروژه اجرا کن:

```bash
docker compose up -d db
docker compose ps
```

وضعیت پایگاه داده باید سالم باشد:

```text
healthy
```

## ۲. بخش سرور

برای بار نخست:

```bash
cp .env.example backend/.env
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/python -m app.exercises.seed
```

دستور seed کاتالوگ ۱۷ حرکت فعلی و رابطه جایگزین curated را ثبت یا به‌روزرسانی می‌کند.
اجرای دوباره آن امن است؛ شناسه حرکت‌ها ثابت می‌ماند و رکورد تکراری ساخته نمی‌شود.

سپس سرور را اجرا کن:

```bash
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## ۳. رابط کاربری

در یک پایانه جدا:

```bash
cd frontend
npm install
npm run dev
```

برنامه در این نشانی باز می‌شود:

```text
http://localhost:5173
```

## ۴. مسیر آزمایش دستی

این ترتیب را در مرورگر بررسی کن:

1. ساخت حساب با ایمیل و رمز حداقل هشت‌نویسه‌ای
2. انتقال خودکار به داشبورد محافظت‌شده
3. تازه‌سازی صفحه و باقی‌ماندن در حساب
4. تغییر زبان میان فارسی و انگلیسی
5. خروج و انتقال به صفحه ورود
6. ورود دوباره با همان حساب
7. تکمیل پروفایل و باز کردن `/exercises`
8. انتخاب ناحیه بدن و گروه عضلانی، تغییر فیلترها و باز کردن جزئیات حرکت

## ۵. آزمایش‌های خودکار

آزمایش بخش سرور به یک پایگاه داده واقعی نیاز دارد:

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test .venv/bin/pytest
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/mypy app tests
```

آزمایش رابط کاربری:

```bash
cd frontend
npm test
npm run lint
npm run build
```

اگر درگاه پایگاه داده روی دستگاه از قبل اشغال است، نگاشت درگاه را در یک فایل ترکیب
محلی تغییر بده و مقدار دو نشانی پایگاه داده را نیز با همان درگاه هماهنگ کن.
