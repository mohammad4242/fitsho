import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { AppIcon } from "../../shared/AppIcon";
import { useAutoAdvance } from "../publicOnboarding/useAutoAdvance";
import type {
  StructuredExerciseInput,
  StructuredExerciseType,
  TrainingIntensity,
} from "./types";

type Props = {
  initialValue?: StructuredExerciseInput;
  fitnessGoal?: string;
  onBack: () => void;
  onComplete: (value: StructuredExerciseInput) => void;
};

type TrainingDraft = {
  trains: boolean | null;
  exerciseType: StructuredExerciseType | null;
  days: number | null;
  minutes: number | null;
  intensity: TrainingIntensity | null;
};

const durationOptions = [30, 45, 60, 75, 90, 120] as const;

export function NutritionExerciseQuestions({ initialValue, fitnessGoal, onBack, onComplete }: Props) {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage === "en" ? "en" : "fa";
  const initialTraining = initialValue?.trains === true ? initialValue : undefined;
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState<TrainingDraft>({
    trains: initialValue?.trains ?? null,
    exerciseType: initialTraining?.exercise_type ?? null,
    days: initialTraining?.days_per_week ?? null,
    minutes: initialTraining?.minutes_per_session ?? null,
    intensity: initialTraining?.intensity ?? null,
  });
  const { selectAndAdvance, resetAdvancing } = useAutoAdvance();
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  });

  const questions = draft.trains === false
    ? (["trains"] as const)
    : (["trains", "type", "days", "duration", "intensity"] as const);
  const question = questions[Math.min(index, questions.length - 1)];
  const l = (fa: string, en: string) => language === "en" ? en : fa;
  const titles = {
    trains: l("در حال حاضر تمرین منظم داری؟", "Do you currently train regularly?"),
    type: l("نوع اصلی تمرینت چیست؟", "What is your main type of exercise?"),
    days: l("چند روز در هفته تمرین می‌کنی؟", "How many days do you train each week?"),
    duration: l("هر جلسه معمولاً چقدر طول می‌کشد؟", "How long is a typical session?"),
    intensity: l("شدت معمول تمرینت چقدر است؟", "What is your usual training intensity?"),
  } as const;

  function submit(event: FormEvent) {
    event.preventDefault();
  }

  function handleBack() {
    resetAdvancing();
    if (index === 0) onBack();
    else setIndex((current) => current - 1);
  }

  const blockedGoal = question === "trains" && draft.trains === false && (fitnessGoal === "build_muscle" || fitnessGoal === "muscle_gain");

  function handleTrains(trains: boolean) {
    if (trains) {
      selectAndAdvance(
        () => setDraft((current) => ({ ...current, trains: true })),
        () => setIndex((current) => current + 1),
      );
      return;
    }

    setDraft({ trains: false, exerciseType: null, days: null, minutes: null, intensity: null });
    if (fitnessGoal === "build_muscle" || fitnessGoal === "muscle_gain") {
      return;
    }
    selectAndAdvance(
      () => undefined,
      () => onCompleteRef.current({ trains: false }),
    );

  }

  return (
    <section className="guided-question" aria-labelledby="nutrition-exercise-title">
      <div className="guided-question__nav">
        <button
          type="button"
          className="guided-back-button"
          onClick={handleBack}
          aria-label={l("بازگشت", "Back")}
        >
          <AppIcon name="arrow" />
        </button>
      </div>
      <div className="public-onboarding-progress">
        <span>{l(`تمرین ${index + 1} از ${questions.length}`, `Exercise ${index + 1} of ${questions.length}`)}</span>
        <progress value={index + 1} max={questions.length} />
      </div>
      <h1 className="fitsho-display" id="nutrition-exercise-title">{titles[question]}</h1>
      <p>{l("فقط همین اطلاعات برای جلوگیری از دوباره‌شماری انرژی لازم است.", "We only use these details to avoid double-counting your energy needs.")}</p>
      <form className="guided-question__form" onSubmit={submit}>
        <div className="guided-choice-grid">
          {question === "trains" && (
            <>
              <button
                className={draft.trains === true ? "is-selected" : ""}
                type="button"
                onClick={() => handleTrains(true)}
              >
                {l("منظم تمرین می‌کنم", "I train regularly")}
              </button>
              <button
                className={draft.trains === false ? "is-selected" : ""}
                type="button"
                onClick={() => handleTrains(false)}
              >
                {l("تمرین نمی‌کنم", "I do not train")}
              </button>
            </>
          )}
          {question === "type" && ([
            ["resistance", l("تمرین مقاومتی", "Resistance training")],
            ["endurance", l("تمرین هوازی و استقامتی", "Endurance training")],
            ["mixed", l("تمرین ترکیبی", "Mixed training")],
            ["other", l("نوع دیگر", "Other exercise")],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              className={draft.exerciseType === value ? "is-selected" : ""}
              type="button"
              onClick={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, exerciseType: value })),
                () => setIndex((current) => current + 1),
              )}
            >
              {label}
            </button>
          ))}
          {question === "days" && [1, 2, 3, 4, 5, 6, 7].map((value) => (
            <button
              key={value}
              className={draft.days === value ? "is-selected" : ""}
              type="button"
              onClick={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, days: value })),
                () => setIndex((current) => current + 1),
              )}
            >
              {l(`${new Intl.NumberFormat("fa-IR").format(value)} روز در هفته`, `${value} days per week`)}
            </button>
          ))}
          {question === "duration" && durationOptions.map((value, optionIndex) => {
            const labels = [l("۲۰–۳۰ دقیقه", "20–30 minutes"), l("۳۰–۴۵ دقیقه", "30–45 minutes"), l("۴۵–۶۰ دقیقه", "45–60 minutes"), l("۶۰–۷۵ دقیقه", "60–75 minutes"), l("۷۵–۹۰ دقیقه", "75–90 minutes"), l("بیش از ۹۰ دقیقه", "More than 90 minutes")];
            return (
              <button
                key={value}
                className={draft.minutes === value ? "is-selected" : ""}
                type="button"
                onClick={() => selectAndAdvance(
                  () => setDraft((current) => ({ ...current, minutes: value })),
                  () => setIndex((current) => current + 1),
                )}
              >
                {labels[optionIndex]}
              </button>
            );
          })}
          {question === "intensity" && ([
            ["light", l("سبک", "Light")],
            ["moderate", l("متوسط", "Moderate")],
            ["vigorous", l("شدید", "Vigorous")],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              className={draft.intensity === value ? "is-selected" : ""}
              type="button"
              onClick={() => selectAndAdvance(
                () => setDraft((current) => ({ ...current, intensity: value })),
                () => onCompleteRef.current({
                  trains: true,
                  exercise_type: draft.exerciseType ?? "other",
                  days_per_week: draft.days ?? 1,
                  minutes_per_session: draft.minutes ?? 30,
                  intensity: value,
                }),

              )}
            >
              {label}
            </button>
          ))}
        </div>
        {blockedGoal && (
          <p role="alert">{l("برای این هدف باید هدفت را تغییر بدهی یا مسیر تمرینی را انتخاب کنی.", "For this goal, choose a different goal or select a training path.")}</p>
        )}
      </form>
    </section>
  );
}

