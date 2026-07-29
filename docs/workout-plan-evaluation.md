# چک‌لیست ارزیابی برنامه تمرینی

فیکسچرهای مصنوعی در `backend/tests/workouts/evaluation_fixtures.py` این سناریوها را پوشش می‌دهند:

1. beginner، ۳ روز، gym، ۶۰ دقیقه، muscle gain
2. beginner، ۳ روز، home bodyweight، ۳۰ دقیقه، general fitness
3. intermediate، ۴ روز، gym، ۷۵ دقیقه، fat loss
4. intermediate، ۳ روز، home dumbbell، ۴۵ دقیقه، muscle gain
5. beginner، ۲ روز، gym، ۴۵ دقیقه، lower-back caution
6. intermediate، ۵ روز، gym، ۹۰ دقیقه، shoulder caution

برای ارزیابی دستی یا تست opt-in Zen، در هر پاسخ این موارد را ثبت کن:

- تمام `exercise_id`ها در allowed candidateها هستند و حرکت inactive/non-programmable انتخاب نشده است.
- همه تجهیزات موردنیاز هر حرکت با محل و setup کاربر سازگار است.
- caution tag ناسازگار وجود ندارد؛ lower-back و shoulder سناریوهای بالا جداگانه بررسی شوند.
- تعداد روزها دقیق است و شماره روزها از ۱ شروع می‌شود.
- ست، تکرار، rest و RIR داخل policy هستند و زمان محاسبه‌شده backend از زمان جلسه عبور نمی‌کند.
- در هر هفته، حرکت‌های compound و patternهای اصلی توزیع معقول دارند و تکرار غیرضروری کم است.
- برای beginner حرکت‌ها پایدار و مناسب‌اند و compoundهای بزرگ پیش از isolationها آمده‌اند.
- روزها یک کپی تصادفی از یکدیگر نیستند و فقط isolation ندارند وقتی compound مناسب موجود است.
- تولیدهای تکراری با ورودی و candidate یکسان از نظر شناسه‌های معتبر و محدودیت‌ها سازگار می‌مانند.

در صورت پاسخ نامعتبر، گزارش باید شامل نام fixture، model، نسخه prompt/policy، hash candidate، زمان
پاسخ و کد خطای امن باشد؛ نام کاربر، ایمیل، تاریخ تولد، کلید API یا متن حساس profile را ثبت نکن.

این چک‌لیست تضمین پزشکی، درمانی یا اعتبارسنجی بالینی نیست.
