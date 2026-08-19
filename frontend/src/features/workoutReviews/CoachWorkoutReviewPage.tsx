import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { AuthenticatedHeader } from "../../shared/AuthenticatedHeader";
import {
  approveWorkoutReview,
  claimWorkoutReview,
  getWorkoutReview,
  listWorkoutReviews,
  renewWorkoutReview,
  saveWorkoutReviewDraft,
} from "./api";
import type {
  WorkoutReviewDayDraft,
  WorkoutReviewDetail,
  WorkoutReviewExerciseDraft,
  WorkoutReviewQueueItem,
  WorkoutReviewQueueView,
} from "./types";
import "./coachWorkoutReview.css";

const queueViews: WorkoutReviewQueueView[] = ["pending", "mine", "approved"];

export function CoachWorkoutReviewPage() {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const fa = i18n.resolvedLanguage !== "en";
  const l = useCallback((faText: string, enText: string) => (fa ? faText : enText), [fa]);
  const [view, setView] = useState<WorkoutReviewQueueView>("pending");
  const [queue, setQueue] = useState<WorkoutReviewQueueItem[]>([]);
  const [selected, setSelected] = useState<WorkoutReviewDetail | null>(null);
  const [draft, setDraft] = useState<WorkoutReviewDayDraft[]>([]);
  const [coachNote, setCoachNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readOnly = selected?.status === "approved";

  const loadQueue = useCallback(async (nextView: WorkoutReviewQueueView) => {
    setLoading(true);
    setError(null);
    try {
      setQueue(await listWorkoutReviews(nextView));
    } catch {
      setError(l("صف بازبینی دریافت نشد. دوباره تلاش کن.", "The review queue could not be loaded. Try again."));
    } finally {
      setLoading(false);
    }
  }, [l]);

  useEffect(() => {
    void loadQueue(view);
  }, [loadQueue, view]);

  useEffect(() => {
    if (selected?.status !== "claimed") return;
    const timer = window.setInterval(() => {
      void renewWorkoutReview(selected.id)
        .then((updated) => setSelected(updated))
        .catch(() => setError(l("زمان بازبینی منقضی شد؛ پرونده را دوباره باز کن.", "The review lease expired. Reopen the case.")));
    }, 8 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [l, selected?.id, selected?.status]);

  function openDetail(detail: WorkoutReviewDetail) {
    setSelected(detail);
    setDraft(structuredClone(detail.draft?.days ?? []));
    setCoachNote(detail.coach_note ?? "");
    setError(null);
  }

  async function openReview(item: WorkoutReviewQueueItem) {
    setBusy(true);
    setError(null);
    try {
      openDetail(
        item.status === "pending"
          ? await claimWorkoutReview(item.id)
          : await getWorkoutReview(item.id),
      );
      await loadQueue(item.status === "pending" ? "mine" : view);
    } catch {
      setError(l("این پرونده در اختیار مربی دیگری است یا دیگر قابل بررسی نیست.", "Another coach owns this case, or it is no longer reviewable."));
      await loadQueue(view);
    } finally {
      setBusy(false);
    }
  }

  function updateExercise(
    dayIndex: number,
    exerciseIndex: number,
    patch: Partial<WorkoutReviewExerciseDraft>,
  ) {
    setDraft((current) => current.map((day, index) => index !== dayIndex ? day : {
      ...day,
      exercises: day.exercises.map((exercise, itemIndex) => (
        itemIndex === exerciseIndex ? { ...exercise, ...patch } : exercise
      )),
    }));
  }

  async function saveDraft() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      openDetail(await saveWorkoutReviewDraft(selected.id, {
        expected_revision: selected.draft_revision,
        coach_note: coachNote.trim() || null,
        days: draft,
      }));
    } catch {
      setError(l("پیش‌نویس معتبر نیست یا نسخه جدیدتری ثبت شده است.", "The draft is invalid or a newer revision exists."));
    } finally {
      setBusy(false);
    }
  }

  async function approve() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await approveWorkoutReview(selected.id, selected.draft_revision);
      setSelected(null);
      setDraft([]);
      setView("approved");
      await loadQueue("approved");
    } catch {
      setError(l("تأیید انجام نشد؛ خطاهای برنامه یا زمان بازبینی را بررسی کن.", "Approval failed. Check the plan errors or review lease."));
    } finally {
      setBusy(false);
    }
  }

  const leaseLabel = useMemo(() => {
    if (!selected?.lease_expires_at) return l("بدون قفل فعال", "No active lease");
    return new Intl.DateTimeFormat(fa ? "fa-IR" : "en", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(selected.lease_expires_at));
  }, [fa, l, selected?.lease_expires_at]);

  return (
    <div className="coach-review-shell" dir={fa ? "rtl" : "ltr"}>
      <AuthenticatedHeader />
      <main className="coach-review-page">
        <header className="coach-review-hero">
          <button className="coach-review-back" type="button" onClick={() => navigate(-1)}>
            {l("بازگشت", "Back")}
          </button>
          <div>
            <p>{l("میز کار مربی", "Coach desk")}</p>
            <h1 className="fitsho-display">{l("بازبینی برنامه‌های تمرینی", "Workout plan reviews")}</h1>
            <span>{l("نسخه اولیه فعال می‌ماند تا نسخه تو با اعتبارسنجی کامل تأیید شود.", "The initial plan stays active until your validated version is approved.")}</span>
          </div>
          <aside className="coach-review-lease" aria-label={l("زمان قفل بازبینی", "Review lease time")}>
            <span aria-hidden="true" />
            <small>{l("قفل بازبینی تا", "Review lease until")}</small>
            <strong>{leaseLabel}</strong>
          </aside>
        </header>

        {error && <p className="coach-review-error" role="alert">{error}</p>}

        <div className="coach-review-workspace">
          <aside className="coach-review-queue">
            <div className="coach-review-tabs" role="tablist" aria-label={l("صف‌های بازبینی", "Review queues")}>
              {queueViews.map((item) => (
                <button
                  key={item}
                  type="button"
                  role="tab"
                  aria-selected={view === item}
                  onClick={() => { setView(item); setSelected(null); }}
                >
                  {queueTitle(item, fa)}
                </button>
              ))}
            </div>
            {loading && <p role="status">{l("در حال دریافت پرونده‌ها…", "Loading cases…")}</p>}
            {!loading && queue.length === 0 && (
              <p className="coach-review-empty">{l("در این صف پرونده‌ای نیست.", "This queue is clear.")}</p>
            )}
            <div className="coach-review-cases">
              {queue.map((item) => (
                <article key={item.id} className={selected?.id === item.id ? "is-selected" : undefined}>
                  <small>{item.member_display_name ?? l("کاربر فیتشو", "Fitsho member")}</small>
                  <strong>{humanize(item.fitness_goal, fa)}</strong>
                  <span>{humanize(item.experience_level, fa)}</span>
                  <button type="button" disabled={busy} onClick={() => void openReview(item)}>
                    {item.status === "pending" ? l("شروع بازبینی", "Start review") : l("مشاهده پرونده", "Open case")}
                  </button>
                </article>
              ))}
            </div>
          </aside>

          <section className="coach-review-canvas" aria-live="polite">
            {!selected && (
              <div className="coach-review-placeholder">
                <span aria-hidden="true">↗</span>
                <h2>{l("یک برنامه را از صف انتخاب کن", "Choose a plan from the queue")}</h2>
                <p>{l("پس از گرفتن پرونده، نسخه اولیه و ابزار ویرایش کنار هم نمایش داده می‌شوند.", "After claiming it, the source version and editing tools appear together.")}</p>
              </div>
            )}
            {selected && (
              <>
                <header className="coach-review-case-header">
                  <div>
                    <small>{l("پرونده", "Case")}</small>
                    <h2>{selected.member_display_name ?? l("کاربر فیتشو", "Fitsho member")}</h2>
                  </div>
                  <span data-status={selected.status}>{statusTitle(selected.status, fa)}</span>
                </header>

                <div className="coach-review-profile-strip">
                  <span>{l("هدف", "Goal")}<strong>{humanize(selected.fitness_goal, fa)}</strong></span>
                  <span>{l("سابقه", "Experience")}<strong>{humanize(selected.experience_level, fa)}</strong></span>
                  <span>{l("مدت", "Duration")}<strong>{selected.source_plan.plan_duration_weeks} {l("هفته", "weeks")}</strong></span>
                </div>

                <div className="coach-review-version-labels">
                  <span>{l("نسخه اولیه — فقط خواندنی", "Initial version — read only")}</span>
                  <span>{readOnly ? l("نسخه تأییدشده", "Approved version") : l("پیش‌نویس مربی", "Coach draft")}</span>
                </div>

                <div className="coach-review-days">
                  {draft.map((day, dayIndex) => (
                    <article key={day.day_number} className="coach-review-day">
                      <header>
                        <span>{String(day.day_number).padStart(2, "0")}</span>
                        <h3>{l(`روز ${faNumber(day.day_number)}`, `Day ${day.day_number}`)}</h3>
                      </header>
                      {day.exercises.map((exercise, exerciseIndex) => {
                        const labelSuffix = l(
                          `روز ${faNumber(day.day_number)} حرکت ${faNumber(exercise.order_index)}`,
                          `day ${day.day_number} exercise ${exercise.order_index}`,
                        );
                        return (
                          <fieldset key={exercise.order_index} disabled={busy || readOnly}>
                            <legend>{l(`حرکت ${faNumber(exercise.order_index)}`, `Exercise ${exercise.order_index}`)}</legend>
                            <label>
                              {l("انتخاب حرکت", "Exercise")}
                              <select value={exercise.exercise_id} onChange={(event) => updateExercise(dayIndex, exerciseIndex, { exercise_id: event.target.value })}>
                                {selected.exercise_options.map((option) => (
                                  <option key={option.id} value={option.id}>{fa ? option.name_fa : option.name_en}</option>
                                ))}
                              </select>
                            </label>
                            <div className="coach-review-prescription">
                              <NumberField label={l(`تعداد ست ${labelSuffix}`, `Sets ${labelSuffix}`)} value={exercise.sets} onChange={(sets) => updateExercise(dayIndex, exerciseIndex, { sets })} />
                              <NumberField label={l(`حداقل تکرار ${labelSuffix}`, `Minimum reps ${labelSuffix}`)} value={exercise.reps_min} onChange={(reps_min) => updateExercise(dayIndex, exerciseIndex, { reps_min })} />
                              <NumberField label={l(`حداکثر تکرار ${labelSuffix}`, `Maximum reps ${labelSuffix}`)} value={exercise.reps_max} onChange={(reps_max) => updateExercise(dayIndex, exerciseIndex, { reps_max })} />
                              <NumberField label={`RIR ${labelSuffix}`} value={exercise.rir ?? 0} min={0} max={5} onChange={(rir) => updateExercise(dayIndex, exerciseIndex, { rir })} />
                              <NumberField label={l(`استراحت ${labelSuffix}`, `Rest ${labelSuffix}`)} value={exercise.rest_seconds} step={15} onChange={(rest_seconds) => updateExercise(dayIndex, exerciseIndex, { rest_seconds })} />
                            </div>
                            <label>
                              {l("یادداشت فارسی حرکت", "Persian exercise note")}
                              <textarea value={exercise.notes_fa ?? ""} onChange={(event) => updateExercise(dayIndex, exerciseIndex, { notes_fa: event.target.value || null })} />
                            </label>
                            <label>
                              {l("یادداشت انگلیسی حرکت", "English exercise note")}
                              <textarea dir="ltr" value={exercise.notes_en ?? ""} onChange={(event) => updateExercise(dayIndex, exerciseIndex, { notes_en: event.target.value || null })} />
                            </label>
                          </fieldset>
                        );
                      })}
                    </article>
                  ))}
                </div>

                <label className="coach-review-note">
                  {l("یادداشت مربی برای کاربر", "Coach note for the member")}
                  <textarea disabled={busy || readOnly} value={coachNote} onChange={(event) => setCoachNote(event.target.value)} maxLength={2000} />
                </label>

                {!readOnly && (
                  <footer className="coach-review-actions">
                    <button type="button" disabled={busy} onClick={() => void saveDraft()}>{l("ذخیره پیش‌نویس", "Save draft")}</button>
                    <button className="is-primary" type="button" disabled={busy} onClick={() => void approve()}>{l("تأیید و ارسال برای کاربر", "Approve and send to member")}</button>
                  </footer>
                )}
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

function NumberField({ label, value, onChange, step = 1, min = 1, max }: { label: string; value: number; onChange: (value: number) => void; step?: number; min?: number; max?: number }) {
  return <label>{label}<input aria-label={label} type="number" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function queueTitle(view: WorkoutReviewQueueView, fa: boolean) {
  if (view === "pending") return fa ? "در انتظار بررسی" : "Waiting";
  if (view === "mine") return fa ? "در حال بررسی من" : "My reviews";
  return fa ? "تأییدشده" : "Approved";
}

function statusTitle(status: WorkoutReviewQueueItem["status"], fa: boolean) {
  const labels = {
    pending: fa ? "در انتظار" : "Waiting",
    claimed: fa ? "در حال بررسی" : "In review",
    approved: fa ? "تأییدشده" : "Approved",
    superseded: fa ? "بایگانی‌شده" : "Archived",
  };
  return labels[status];
}

function humanize(value: string | null, fa: boolean) {
  if (!value) return fa ? "ثبت نشده" : "Not provided";
  const labels: Record<string, [string, string]> = {
    build_muscle: ["عضله‌سازی", "Build muscle"],
    lose_weight: ["کاهش وزن", "Lose weight"],
    beginner: ["مبتدی", "Beginner"],
    intermediate: ["متوسط", "Intermediate"],
    advanced: ["پیشرفته", "Advanced"],
  };
  const translated = labels[value];
  return translated ? translated[fa ? 0 : 1] : value.replaceAll("_", " ");
}

function faNumber(value: number) {
  return value.toLocaleString("fa-IR", { useGrouping: false });
}
