# Workout PDF Summary Redesign

## Scope

Refine only the existing backend-generated workout-plan PDF. Keep the current endpoint, ownership
check, frontend Blob download, and existing download button unchanged.

## Typography

Use Vazirmatn for all Persian PDF text. Install the Debian `fonts-vazirmatn` package in the backend
image so the font is available consistently at runtime. Keep DejaVu Sans as the final fallback.

## Content

Keep the PDF concise. It contains:

- the workout-plan title and plan duration;
- each training day's Persian title;
- each exercise's Persian name;
- sets, repetition range, and rest time;
- exercise notes when present;
- program, day, and coach notes when present.

Remove:

- each day's estimated total duration, such as `۲۷ دقیقه`;
- load guidance;
- progression method or rule.

## Exercise Order

Number exercises independently inside each day using Persian digits and a closing parenthesis:
`۱)`, `۲)`, `۳)`. The counter restarts from `۱)` for every training day and follows the persisted
exercise order already supplied by the workout-plan response.

## Verification

Update renderer tests to verify Vazirmatn CSS, per-day numbering and counter reset, absence of day
duration/load guidance/progression rule, preservation of exercise notes, and successful PDF byte
generation. Rebuild the backend image and verify Vazirmatn is available through Fontconfig inside
the container.
