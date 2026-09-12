import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { beforeEach, expect, jest, test } from "@jest/globals";
import { StyleSheet } from "react-native";
import { useState } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));
jest.mock("expo-video", () => ({ VideoView: () => null, useVideoPlayer: () => ({}) }));

import { emptyProfileFormValues, profileInputForOnboarding } from "../onboardingForms";
import type { ProfileFormValues } from "@fitician/core/profile";
import { GuidedSharedProfileQuestions } from "./GuidedSharedProfileQuestions";
import { GuidedTrainingQuestions } from "./GuidedTrainingQuestions";

function renderWithSafeArea(element: React.ReactElement) {
  return render(
    <SafeAreaProvider
      initialMetrics={{
        frame: { height: 800, width: 390, x: 0, y: 0 },
        insets: { bottom: 0, left: 0, right: 0, top: 0 },
      }}
    >
      {element}
    </SafeAreaProvider>,
  );
}

function SharedHarness({ onComplete, onBack }: { onComplete?: () => void; onBack?: () => void }) {
  const [values, setValues] = useState(emptyProfileFormValues);
  return (
    <GuidedSharedProfileQuestions
      onBack={onBack ?? jest.fn()}
      onChange={(field, value) => setValues((current) => ({ ...current, [field]: value }))}
      onComplete={onComplete ?? jest.fn()}
      values={values}
    />
  );
}

function advance() {
  act(() => {
    jest.advanceTimersByTime(140);
  });
}

beforeEach(() => {
  jest.useFakeTimers();
});

test("shows exactly one shared question at a time and keeps the Web five-step order", () => {
  const onComplete = jest.fn();
  renderWithSafeArea(<SharedHarness onComplete={onComplete} />);

  expect(StyleSheet.flatten(screen.getByTestId("public-shared-questions").props.style)).toMatchObject({
    minHeight: 640,
  });
  expect(screen.getByRole("header", { name: "دوست داری چه صدایت کنیم؟" })).toBeTruthy();
  expect(screen.getByText("مرحله 1 از 5")).toBeTruthy();
  expect(screen.getByRole("button", { name: "ادامه" })).toBeTruthy();
  expect(screen.queryByRole("header", { name: "چه تاریخی به دنیا آمدی؟" })).toBeNull();

  fireEvent.changeText(screen.getByLabelText("نام نمایشی"), "سارا");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("header", { name: "چه تاریخی به دنیا آمدی؟" })).toBeTruthy();
  expect(screen.queryByRole("header", { name: "دوست داری چه صدایت کنیم؟" })).toBeNull();

  fireEvent.press(screen.getByTestId("birth-day"));
  fireEvent.press(screen.getByTestId("birth-day-option-12"));
  fireEvent.press(screen.getByTestId("birth-month"));
  fireEvent.press(screen.getByTestId("birth-month-option-5"));
  fireEvent.press(screen.getByTestId("birth-year"));
  fireEvent.press(screen.getByTestId("birth-year-option-1992"));

  expect(
    StyleSheet.flatten(screen.getByTestId("public-birth-date-grid").props.style),
  ).toMatchObject({ flexDirection: "column" });

  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("header", { name: "جنسیتت چیست؟" })).toBeTruthy();
  expect(screen.getAllByRole("radio")).toHaveLength(2);
  expect(screen.getByRole("radio", { name: "زن" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "مرد" })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: "سایر" })).toBeNull();
  expect(screen.queryByRole("radio", { name: "ترجیح می‌دهم نگویم" })).toBeNull();

  fireEvent.press(screen.getByRole("radio", { name: "زن" }));
  advance();
  expect(screen.getByRole("header", { name: "قد و وزنت چقدر است؟" })).toBeTruthy();
  expect(screen.getByText("مرحله 4 از 5")).toBeTruthy();

  fireEvent.changeText(screen.getByLabelText("قد (سانتی‌متر)"), "168");
  fireEvent.changeText(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "64");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("header", { name: "هدف اصلی تو چیست؟" })).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "عضله‌سازی 💪" }));
  advance();
  expect(onComplete).toHaveBeenCalledTimes(1);
});

test("requires Web unusual-value confirmation before leaving the body question", () => {
  renderWithSafeArea(<SharedHarness />);

  fireEvent.changeText(screen.getByLabelText("نام نمایشی"), "سارا");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByTestId("birth-day"));
  fireEvent.press(screen.getByTestId("birth-day-option-12"));
  fireEvent.press(screen.getByTestId("birth-month"));
  fireEvent.press(screen.getByTestId("birth-month-option-5"));
  fireEvent.press(screen.getByTestId("birth-year"));
  fireEvent.press(screen.getByTestId("birth-year-option-1992"));
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "زن" }));
  advance();

  fireEvent.changeText(screen.getByLabelText("قد (سانتی‌متر)"), "135");
  fireEvent.changeText(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "64");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByText("این مقادیر درست هستند.")).toBeTruthy();
  expect(screen.getByRole("header", { name: "قد و وزنت چقدر است؟" })).toBeTruthy();
  fireEvent.press(screen.getByRole("checkbox", { name: "این مقادیر درست هستند." }));
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  expect(screen.getByRole("header", { name: "هدف اصلی تو چیست؟" })).toBeTruthy();
});

test("shared back returns to the previous question and exits from question one", () => {
  const onBack = jest.fn();
  renderWithSafeArea(<SharedHarness onBack={onBack} />);

  fireEvent.changeText(screen.getByLabelText("نام نمایشی"), "سارا");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("button", { name: "بازگشت" }));
  expect(screen.getByRole("header", { name: "دوست داری چه صدایت کنیم؟" })).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "بازگشت" }));
  expect(onBack).toHaveBeenCalledTimes(1);
});

test("uses the Web gender card scale, body range hints, and goal labels", () => {
  renderWithSafeArea(<SharedHarness />);

  fireEvent.changeText(screen.getByLabelText("نام نمایشی"), "سارا");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByTestId("birth-day"));
  fireEvent.press(screen.getByTestId("birth-day-option-12"));
  fireEvent.press(screen.getByTestId("birth-month"));
  fireEvent.press(screen.getByTestId("birth-month-option-5"));
  fireEvent.press(screen.getByTestId("birth-year"));
  fireEvent.press(screen.getByTestId("birth-year-option-1992"));
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));

  const female = screen.getByRole("radio", { name: "زن" });
  expect(StyleSheet.flatten(female.props.style)).toMatchObject({
    flexDirection: "column",
    minHeight: 116,
  });

  fireEvent.press(female);
  advance();
  expect(screen.getByText("۱۲۰ تا ۲۳۰ سانتی‌متر")).toBeTruthy();
  expect(screen.getByText("۳۵ تا ۳۰۰ کیلوگرم")).toBeTruthy();
  fireEvent.changeText(screen.getByLabelText("قد (سانتی‌متر)"), "168");
  fireEvent.changeText(screen.getByLabelText("وزن فعلی (کیلوگرم)"), "64");
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));

  expect(screen.getByRole("radio", { name: "کاهش وزن 🔻⬆️" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "افزایش وزن 🔺️⬇️" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "چربی‌سوزی 🔥" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "عضله‌سازی 💪" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "چربی‌سوزی + عضله‌سازی 🔥💪" })).toBeTruthy();
});

function TrainingHarness({
  initialValues,
  onComplete,
  onBack,
  onChange,
}: {
  initialValues?: ProfileFormValues;
  onComplete?: (values: ProfileFormValues) => void;
  onBack?: () => void;
  onChange?: (field: string, value: unknown) => void;
}) {
  const [values, setValues] = useState(initialValues ?? emptyProfileFormValues());
  return (
    <GuidedTrainingQuestions
      onBack={onBack ?? jest.fn()}
      onChange={(field, value) => {
        onChange?.(field, value);
        setValues((current) => ({ ...current, [field]: value }));
      }}
      onComplete={onComplete ?? jest.fn()}
      values={values}
    />
  );
}

test("training follows the exact conditional Web order and progress count", () => {
  renderWithSafeArea(<TrainingHarness />);

  expect(screen.getByRole("header", { name: "چقدر سابقه تمرین مداوم داری؟" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "ماه اولمه" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "مبتدی (زیر ۶ ماه)" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "متوسط (۶ ماه تا ۲ سال)" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "پیشرفته (بیش از ۲ سال)" })).toBeTruthy();

  fireEvent.press(screen.getByRole("radio", { name: "مبتدی (زیر ۶ ماه)" }));
  advance();
  expect(screen.getByText("تمرین 2 از 9")).toBeTruthy();
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "۳ روز در هفته" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "باشگاه" }));
  advance();
  expect(screen.getByRole("header", { name: "برای هر جلسه چقدر زمان داری؟" })).toBeTruthy();
  expect(screen.queryByRole("header", { name: "در خانه چه امکاناتی داری؟" })).toBeNull();
  expect(screen.getByText("تمرین 5 از 9")).toBeTruthy();
});

test("home inserts the home-equipment question and cautions keep skip behavior", () => {
  renderWithSafeArea(<TrainingHarness />);

  fireEvent.press(screen.getByRole("radio", { name: "ماه اولمه" }));
  advance();
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "۳ روز در هفته" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "خانه" }));
  advance();
  expect(screen.getByRole("header", { name: "در خانه چه امکاناتی داری؟" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "وزن بدن" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "دمبل" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "کش" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "دمبل + کش" })).toBeTruthy();
  fireEvent.press(screen.getByRole("radio", { name: "وزن بدن" }));
  advance();
  expect(screen.getByText("۲۰ تا ۳۰ دقیقه")).toBeTruthy();
});

test("each home preset synchronizes its setup and canonical equipment", () => {
  const cases = [
    ["وزن بدن", "bodyweight_only", ["bodyweight", "pull_up_bar"]],
    ["دمبل", "dumbbells_available", ["bodyweight", "dumbbell", "pull_up_bar"]],
    ["کش", "resistance_bands_available", ["bodyweight", "resistance_band", "pull_up_bar"]],
    ["دمبل + کش", "dumbbells_and_resistance_bands_available", ["bodyweight", "dumbbell", "resistance_band", "pull_up_bar"]],
  ] as const;

  for (const [label, setup, equipment] of cases) {
    const changes: Array<[string, unknown]> = [];
    const rendered = renderWithSafeArea(
      <TrainingHarness onChange={(field, value) => changes.push([field, value])} />,
    );

    fireEvent.press(screen.getByRole("radio", { name: "ماه اولمه" }));
    advance();
    fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
    fireEvent.press(screen.getByRole("radio", { name: "۳ روز در هفته" }));
    advance();
    fireEvent.press(screen.getByRole("radio", { name: "خانه" }));
    advance();

    expect(screen.getAllByRole("radio")).toHaveLength(4);
    fireEvent.press(screen.getByRole("radio", { name: label }));
    expect(changes.slice(-2)).toEqual([
      ["home_training_setup", setup],
      ["available_equipment", equipment],
    ]);

    rendered.unmount();
    jest.clearAllTimers();
  }
});

test("keeps Web duration, intensity, priority, caution, and week choices", () => {
  const onComplete = jest.fn();
  renderWithSafeArea(<TrainingHarness onComplete={onComplete} />);

  fireEvent.press(screen.getByRole("radio", { name: "مبتدی (زیر ۶ ماه)" }));
  advance();
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "۲ روز در هفته" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "باشگاه" }));
  advance();

  for (const label of ["۲۰ تا ۳۰ دقیقه", "۳۰ تا ۴۵ دقیقه", "۴۵ تا ۶۰ دقیقه", "۶۰ تا ۷۵ دقیقه", "۷۵ تا ۹۰ دقیقه", "بیش از ۹۰ دقیقه"]) {
    expect(screen.getByRole("radio", { name: label })).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("radio", { name: "۳۰ تا ۴۵ دقیقه" }));
  advance();
  for (const label of ["سبک", "متوسط", "شدید"]) {
    expect(screen.getByRole("radio", { name: label })).toBeTruthy();
  }
  fireEvent.press(screen.getByRole("radio", { name: "متوسط" }));
  advance();
  expect(screen.getByRole("radio", { name: "تمرکز ویژه‌ای ندارم" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "سینه" })).toBeTruthy();
  fireEvent.press(screen.getByRole("radio", { name: "تمرکز ویژه‌ای ندارم" }));
  advance();

  fireEvent.press(screen.getByRole("checkbox", { name: "احتیاط برای کمر" }));
  fireEvent.press(screen.getByRole("checkbox", { name: "احتیاط برای زانو" }));
  expect(screen.getByRole("checkbox", { name: "احتیاط برای کمر" }).props.accessibilityState).toMatchObject({ checked: true });
  expect(screen.getByRole("checkbox", { name: "احتیاط برای زانو" }).props.accessibilityState).toMatchObject({ checked: true });
  fireEvent.press(screen.getByRole("button", { name: "رد کردن این سؤال" }));

  expect(screen.getByRole("radio", { name: "۴ هفته" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "۶ هفته" })).toBeTruthy();
  expect(screen.getByRole("radio", { name: "۸ هفته" })).toBeTruthy();
  fireEvent.press(screen.getByRole("radio", { name: "۶ هفته" }));
  advance();
  expect(onComplete).toHaveBeenCalledTimes(1);
});

test("maps home equipment before the final public training submission", () => {
  const initialValues = emptyProfileFormValues();
  Object.assign(initialValues, {
    birth_date: "1992-05-12",
    current_weight_kg: "64",
    display_name: "Sara",
    fitness_goal: "build_muscle",
    height_cm: "168",
    sex: "female",
  });
  const onComplete = jest.fn<(values: ProfileFormValues) => void>();
  renderWithSafeArea(<TrainingHarness initialValues={initialValues} onComplete={onComplete} />);

  fireEvent.press(screen.getByRole("radio", { name: "مبتدی (زیر ۶ ماه)" }));
  advance();
  fireEvent.press(screen.getByRole("button", { name: "ادامه" }));
  fireEvent.press(screen.getByRole("radio", { name: "۳ روز در هفته" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "خانه" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "وزن بدن" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "۳۰ تا ۴۵ دقیقه" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "متوسط" }));
  advance();
  fireEvent.press(screen.getByRole("radio", { name: "تمرکز ویژه‌ای ندارم" }));
  advance();
  fireEvent.press(screen.getByRole("button", { name: "رد کردن این سؤال" }));
  fireEvent.press(screen.getByRole("radio", { name: "۶ هفته" }));
  advance();

  expect(onComplete).toHaveBeenCalledTimes(1);
  const completedValues = onComplete.mock.calls[0]?.[0];
  expect(completedValues).toBeDefined();
  expect(() => profileInputForOnboarding(completedValues!, new Date("2026-09-11T00:00:00Z"))).not.toThrow();
});
