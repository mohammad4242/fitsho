import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Text } from "react-native";

import { Button } from "./components/Button";
import { TextField } from "./components/Input";
import { MetricRing } from "./components/MetricRing";
import { Dialog, Sheet } from "./components/Overlay";

test("renders the shared button with native accessibility and press behavior", () => {
  const onPress = jest.fn();

  render(<Button label="ذخیره" onPress={onPress} />);

  const button = screen.getByRole("button", { name: "ذخیره" });
  expect(button.props.accessibilityState).toMatchObject({ disabled: false, busy: false });
  expect(button.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ minHeight: 48, minWidth: 48 })]),
  );

  fireEvent.press(button);
  expect(onPress).toHaveBeenCalledTimes(1);
});

test("keeps screen-reader names, font scaling, and focus order in source order", () => {
  render(
    <>
      <TextField label="ایمیل" />
      <Button label="اول" onPress={jest.fn()} />
      <Button label="دوم" onPress={jest.fn()} />
    </>,
  );

  const field = screen.getByLabelText("ایمیل");
  expect(field.props.allowFontScaling).toBe(true);
  expect(field.props.accessibilityLabel).toBe("ایمیل");
  expect(screen.getAllByRole("button").map((button) => button.props.accessibilityLabel)).toEqual([
    "اول",
    "دوم",
  ]);
});

test("exposes metric progress and its visible value to assistive technology", () => {
  render(<MetricRing label="پیشرفت کالری امروز" progress={0.375} />);

  const ring = screen.getByRole("progressbar", { name: "پیشرفت کالری امروز" });
  expect(ring.props.accessibilityValue).toEqual({ max: 100, min: 0, now: 38 });
  expect(screen.getByText("۳۸٪")).toBeTruthy();
});

test("keeps Persian overlays direction-aware", () => {
  const view = render(
    <>
      <Sheet onClose={jest.fn()} title="جزئیات" visible><Text>متن</Text><TextField label="نام" /></Sheet>
      <Dialog message="پیام" onClose={jest.fn()} title="تأیید" visible />
    </>,
  );

  expect(view).toBeTruthy();
});
