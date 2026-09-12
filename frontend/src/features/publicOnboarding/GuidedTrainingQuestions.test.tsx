import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { GuidedTrainingQuestions } from "./GuidedTrainingQuestions";

const values = {
  display_name: "Sara", birth_date: "2000-05-14", sex: "female" as const,
  height_cm: "165", current_weight_kg: "62", shoulder_circumference_cm: "",
  waist_circumference_cm: "", hip_circumference_cm: "", fitness_goal: "fat_loss" as const,
  experience_level: "" as const, training_days_per_week: "", preferred_weekdays: [], priority_muscle: "" as const,
  training_location: "" as const,
  home_training_setup: "" as const, session_duration_minutes: "",
  available_equipment: [],
  training_intensity: "" as const,
  training_age_months: "",
  training_cautions: null, plan_duration_weeks: "4",
};

function TrainingHarness({ allowNoTraining = false, onNoTraining = vi.fn() }: { allowNoTraining?: boolean; onNoTraining?: () => void }) {
  const [formValues, setFormValues] = useState(values);
  const [completed, setCompleted] = useState(false);
  return <>
    <GuidedTrainingQuestions
      values={formValues}
      onChange={(field, value) => setFormValues((current) => ({ ...current, [field]: value }))}
      onBack={() => undefined}
      onComplete={() => setCompleted(true)}
      allowNoTraining={allowNoTraining}
      onNoTraining={onNoTraining}
    />
    <output data-testid="home-state">
      {formValues.home_training_setup}:{formValues.available_equipment?.join(",")}
    </output>
    {formValues.training_cautions !== null && <p>cautions-set</p>}
    {completed && <p>completed</p>}
  </>;
}

it("uses fixed experience, weekly-day, and workout-time choices with auto-advancing", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  render(<TrainingHarness />);

  expect(screen.getByRole("heading", { name: "چقدر سابقه تمرین مداوم داری؟" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ماه اولمه" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();

  // Experience auto-advances to trainingAge
  await user.click(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" }));

  // trainingAge requires Continue
  await user.type(await screen.findByLabelText("سابقه تمرین به ماه"), "24");
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  // days auto-advances to location
  expect(await screen.findByRole("heading", { name: "چند روز در هفته تمرین می‌کنی؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "۴ روز در هفته" }));

  // location: gym auto-advances and skips home-equipment to duration
  expect(await screen.findByRole("heading", { name: "کجا تمرین می‌کنی؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "باشگاه" }));

  // duration auto-advances to intensity
  expect(await screen.findByRole("heading", { name: "برای هر جلسه چقدر زمان داری؟" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "۲۰ تا ۳۰ دقیقه" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "بیش از ۹۰ دقیقه" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "۴۵ تا ۶۰ دقیقه" }));

  // intensity auto-advances to priority
  expect(await screen.findByRole("heading", { name: "شدت معمول تمرینت چقدر است؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "متوسط" }));

  // priority muscle auto-advances to cautions
  expect(await screen.findByRole("heading", { name: "دوست داری در برنامه روی کدام عضله بیشتر تمرکز شود؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "بالاتنه" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "جلو بازو" }));

  // cautions is multi-select: requires Continue or Skip
  expect(await screen.findByRole("heading", { name: "برای تمرین مورد احتیاطی داری؟" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "ادامه" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByText("cautions-set")).toBeInTheDocument();

  // weeks auto-advances and completes
  expect(await screen.findByRole("heading", { name: "این برنامه چند هفته باشد؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "۴ هفته" }));

  expect(await screen.findByText("completed")).toBeInTheDocument();
});

it("renders all home presets and synchronizes setup and inventory", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  render(<TrainingHarness />);

  await user.click(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" }));
  await user.click(await screen.findByRole("button", { name: "ادامه" }));
  await user.click(await screen.findByRole("button", { name: "۳ روز در هفته" }));

  expect(await screen.findByRole("heading", { name: "کجا تمرین می‌کنی؟" })).toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "خانه" }));

  // Home equipment question appears and auto-advances
  expect(await screen.findByRole("heading", { name: "در خانه چه امکاناتی داری؟" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();

  const presets = [
    ["وزن بدن", "bodyweight_only", "bodyweight,pull_up_bar"],
    ["دمبل", "dumbbells_available", "bodyweight,dumbbell,pull_up_bar"],
    ["کش", "resistance_bands_available", "bodyweight,resistance_band,pull_up_bar"],
    [
      "دمبل + کش",
      "dumbbells_and_resistance_bands_available",
      "bodyweight,dumbbell,resistance_band,pull_up_bar",
    ],
  ] as const;
  for (const [label, setup, equipment] of presets) {
    for (const [nextLabel] of presets) {
      expect(screen.getByRole("button", { name: nextLabel })).toBeInTheDocument();
    }
    await user.click(screen.getByRole("button", { name: label }));
    expect(screen.getByTestId("home-state")).toHaveTextContent(`${setup}:${equipment}`);
    if (setup !== "dumbbells_and_resistance_bands_available") {
      await screen.findByRole("heading", { name: "برای هر جلسه چقدر زمان داری؟" });
      await user.click(screen.getByRole("button", { name: "بازگشت" }));
      await screen.findByRole("heading", { name: "در خانه چه امکاناتی داری؟" });
    }
  }

  expect(await screen.findByRole("heading", { name: "برای هر جلسه چقدر زمان داری؟" })).toBeInTheDocument();
});

it("cautions allows multiple selections without auto-advancing", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  render(<TrainingHarness />);

  await user.click(screen.getByRole("button", { name: "مبتدی (زیر ۶ ماه)" }));
  await user.click(await screen.findByRole("button", { name: "ادامه" }));
  await user.click(await screen.findByRole("button", { name: "۳ روز در هفته" }));
  await user.click(await screen.findByRole("button", { name: "باشگاه" }));
  await user.click(await screen.findByRole("button", { name: "۴۵ تا ۶۰ دقیقه" }));
  await user.click(await screen.findByRole("button", { name: "متوسط" }));
  await user.click(await screen.findByRole("button", { name: "تمرکز ویژه‌ای ندارم" }));

  expect(await screen.findByRole("heading", { name: "برای تمرین مورد احتیاطی داری؟" })).toBeInTheDocument();
  const kneeBtn = screen.getByRole("button", { name: "احتیاط برای زانو" });
  const shoulderBtn = screen.getByRole("button", { name: "احتیاط برای شانه" });

  await user.click(kneeBtn);
  // Does not advance! Both knee and shoulder are still on screen
  expect(kneeBtn).toHaveClass("is-selected");
  expect(shoulderBtn).not.toHaveClass("is-selected");

  await user.click(shoulderBtn);
  expect(kneeBtn).toHaveClass("is-selected");
  expect(shoulderBtn).toHaveClass("is-selected");

  // Still on cautions question
  expect(screen.getByRole("heading", { name: "برای تمرین مورد احتیاطی داری؟" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ادامه" }));

  expect(await screen.findByRole("heading", { name: "این برنامه چند هفته باشد؟" })).toBeInTheDocument();
});

it("offers no-training only for nutrition and skips all training details", async () => {
  await i18n.changeLanguage("fa");
  const user = userEvent.setup();
  const onNoTraining = vi.fn();
  render(<TrainingHarness allowNoTraining onNoTraining={onNoTraining} />);

  expect(screen.queryByRole("button", { name: "ادامه" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "تمرین نمی‌کنم" }));

  await vi.waitFor(() => expect(onNoTraining).toHaveBeenCalledOnce());
  expect(screen.queryByRole("heading", { name: "چند روز در هفته تمرین می‌کنی؟" })).not.toBeInTheDocument();
});

it("does not offer no-training in the required training flow", async () => {
  await i18n.changeLanguage("fa");
  render(<TrainingHarness />);

  expect(screen.queryByRole("button", { name: "تمرین نمی‌کنم" })).not.toBeInTheDocument();
});
