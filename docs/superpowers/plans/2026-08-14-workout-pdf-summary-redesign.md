# Workout PDF Summary Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Persian workout PDF more attractive and concise with Vazirmatn typography and per-day exercise numbering.

**Architecture:** Keep the existing renderer and download flow. Adjust only its HTML/CSS and Docker font package, using the response list order as the canonical exercise order and resetting display numbering inside each day.

**Tech Stack:** Python 3.12, WeasyPrint 69, Vazirmatn, pytest, Docker

## Global Constraints

- Keep the existing authenticated PDF endpoint and frontend action unchanged.
- Use Vazirmatn with DejaVu Sans fallback.
- Number exercises as Persian `۱)`, `۲)`, `۳)` and restart per day.
- Remove day duration, load guidance, and progression rule.
- Keep title, plan duration, day titles, Persian exercise names, sets, reps, rest, and useful notes.
- Preserve unrelated working-tree changes and stage only task files.

---

### Task 1: Concise numbered PDF content

**Files:**
- Modify: `backend/tests/workouts/test_pdf.py`
- Modify: `backend/app/workouts/pdf.py`

**Interfaces:**
- Consumes: the existing `WorkoutPlanResponse.days[*].exercises` order.
- Produces: unchanged `build_workout_plan_html(plan: WorkoutPlanResponse) -> str` and `render_workout_plan_pdf(plan: WorkoutPlanResponse) -> bytes`.

- [ ] **Step 1: Write failing renderer assertions**

```python
def test_html_uses_vazirmatn_and_numbers_exercises_per_day() -> None:
    plan = _plan_response()
    plan.days.append(second_day_response())
    html = build_workout_plan_html(plan)
    assert 'font-family: "Vazirmatn", "DejaVu Sans", sans-serif' in html
    assert html.count('<span class="exercise-number">۱)</span>') == 2
    assert '<span class="exercise-number">۲)</span>' in html


def test_html_omits_nonessential_duration_and_progression_details() -> None:
    html = build_workout_plan_html(_plan_response())
    assert "۴۵ دقیقه" not in html
    assert "راهنمای وزنه" not in html
    assert "وزنه را تدریجی افزایش بده." not in html
    assert "روش پیشرفت" not in html
    assert "double_progression" not in html
    assert "کنترل‌شده حرکت کن." in html
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py -v`

Expected: FAIL because the renderer still uses DejaVu Sans, has no exercise number markup, and includes removed details.

- [ ] **Step 3: Implement numbering and concise content**

```python
def _render_day(day: WorkoutDayResponse) -> str:
    exercises = "".join(
        _render_exercise(position=position, name=item.exercise.name_fa, sets=item.sets,
                         reps_min=item.reps_min, reps_max=item.reps_max,
                         rest_seconds=item.rest_seconds, notes=item.notes_fa or item.notes_en)
        for position, item in enumerate(day.exercises, start=1)
    )
    return f'<section class="day"><h2>روز {_fa_number(day.day_number)}: {escape(day.title_fa)}</h2>{exercises}</section>'
```

Change `_render_exercise` to accept `position: int`, render
`<span class="exercise-number">{_fa_number(position)})</span>`, and remove its `load_guidance` and
`progression_rule` parameters. Set the body stack to
`font-family: "Vazirmatn", "DejaVu Sans", sans-serif` and keep existing optional notes.

- [ ] **Step 4: Run focused checks and confirm GREEN**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py -v && uv run ruff check app/workouts/pdf.py tests/workouts/test_pdf.py && uv run mypy app/workouts/pdf.py`

Expected: PASS.

### Task 2: Container font availability and final verification

**Files:**
- Modify: `backend/Dockerfile`

**Interfaces:**
- Produces: a backend image where `fc-match Vazirmatn` resolves to `Vazirmatn-Regular.ttf`.

- [ ] **Step 1: Add the runtime font package**

```dockerfile
fonts-vazirmatn \
```

Add it beside `fonts-dejavu-core` in the existing apt package list.

- [ ] **Step 2: Run all relevant checks**

Run: `cd backend && uv run pytest tests/workouts/test_pdf.py tests/workouts/test_workout_plan_api.py -v && uv run ruff check app/workouts/pdf.py tests/workouts/test_pdf.py && uv run mypy app`

Expected: PASS.

- [ ] **Step 3: Build and inspect the real image**

Run: `docker compose build backend && docker compose run --rm --no-deps backend fc-match Vazirmatn`

Expected: output starts with `Vazirmatn-Regular.ttf`.

- [ ] **Step 4: Commit and push**

```bash
git add backend/app/workouts/pdf.py backend/tests/workouts/test_pdf.py backend/Dockerfile
git commit -m "refactor(workouts): simplify Persian workout PDFs"
git push origin main
```

- [ ] **Step 5: Verify repository state**

Run: `git status --short --branch && git rev-parse HEAD && git rev-parse origin/main`

Expected: feature files are clean, `HEAD` equals `origin/main`, and unrelated user changes remain untouched.
