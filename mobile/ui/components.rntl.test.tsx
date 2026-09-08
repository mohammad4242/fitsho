import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

import { Button } from "./components/Button";
import { TextField } from "./components/Input";

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
