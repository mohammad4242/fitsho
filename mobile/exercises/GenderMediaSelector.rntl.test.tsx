import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";

jest.mock("@expo/vector-icons", () => ({ MaterialCommunityIcons: () => null }));

import { GenderMediaSelector } from "./GenderMediaSelector";

test("renders compact accessible gender radios and only offers available media", () => {
  const onChange = jest.fn();

  const { rerender } = render(
    <GenderMediaSelector
      available={["male", "female"]}
      language="fa"
      onChange={onChange}
      selected="male"
    />,
  );

  expect(screen.getByRole("radio", { name: "ویدیوی مرد" }).props.accessibilityState).toEqual({
    selected: true,
  });
  expect(screen.getByRole("radio", { name: "ویدیوی زن" })).toBeTruthy();
  fireEvent.press(screen.getByRole("radio", { name: "ویدیوی زن" }));
  expect(onChange).toHaveBeenCalledWith("female");

  rerender(
    <GenderMediaSelector
      available={["male"]}
      language="en"
      onChange={onChange}
      selected="male"
    />,
  );

  expect(screen.getByRole("radio", { name: "Male video" })).toBeTruthy();
  expect(screen.queryByRole("radio", { name: "Female video" })).toBeNull();
});
