import { fireEvent, render, screen } from "@testing-library/react-native";
import { expect, jest, test } from "@jest/globals";
import { Text, TextInput } from "react-native";
import { DisclosureCard } from "./components/DisclosureCard";

jest.mock("./components/AppIcon", () => ({ AppIcon: () => null }));

test("starts collapsed, opens from the whole header, and hides content from accessibility", () => {
  render(<DisclosureCard title="راهنمای اجرا"><Text>قدم اول</Text></DisclosureCard>);
  const header = screen.getByRole("button", { name: "راهنمای اجرا" });
  expect(header.props.accessibilityState.expanded).toBe(false);
  expect(screen.queryByText("قدم اول")).toBeNull();
  fireEvent.press(header);
  expect(screen.getByText("قدم اول")).toBeTruthy();
  expect(header.props.accessibilityState.expanded).toBe(true);
  fireEvent.press(header);
  expect(screen.queryByText("قدم اول")).toBeNull();
});

test("keeps mounted form state when closed and reopened", () => {
  render(<DisclosureCard title="پروفایل"><TextInput accessibilityLabel="نام" defaultValue="سارا" /></DisclosureCard>);
  fireEvent.press(screen.getByRole("button"));
  const input = screen.getByLabelText("نام");
  fireEvent.press(screen.getByRole("button"));
  expect(screen.queryByLabelText("نام")).toBeNull();
  fireEvent.press(screen.getByRole("button"));
  expect(screen.getByLabelText("نام")).toBe(input);
});

test("controlled expansion waits for owner and reports the next value", () => {
  const onExpandedChange = jest.fn();
  const view = render(<DisclosureCard title="جزئیات" expanded={false} onExpandedChange={onExpandedChange}><Text>محتوا</Text></DisclosureCard>);
  fireEvent.press(screen.getByRole("button"));
  expect(onExpandedChange).toHaveBeenCalledWith(true);
  expect(screen.queryByText("محتوا")).toBeNull();
  view.rerender(<DisclosureCard title="جزئیات" expanded onExpandedChange={onExpandedChange}><Text>محتوا</Text></DisclosureCard>);
  expect(screen.getByText("محتوا")).toBeTruthy();
});
