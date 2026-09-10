import { expect, test, vi } from "vitest";
import { createElement, type ReactElement } from "react";
import TestRenderer, { act, type ReactTestRenderer } from "react-test-renderer";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const native = vi.hoisted(() => ({
  ActivityIndicator: "ActivityIndicator",
  Pressable: "Pressable",
  StyleSheet: {
    create: <T extends Record<string, unknown>>(styles: T): T => styles,
  },
  Text: "Text",
  View: "View",
}));

vi.mock("react-native", () => native);
vi.mock("./components/AppIcon", () => ({ AppIcon: "AppIcon" }));
vi.mock("./components/Card", () => ({ Card: "Card" }));

import { DisclosureCard } from "./components/DisclosureCard";
import { GroupedList } from "./components/GroupedList";
import { PageHeading } from "./components/PageHeading";
import { SegmentedControl } from "./components/SegmentedControl";
import { ScreenHeader } from "./components/ScreenHeader";
import { SectionHeader } from "./components/SectionHeader";

function render(element: ReactElement): ReactTestRenderer {
  let renderer: ReactTestRenderer | undefined;
  act(() => {
    renderer = TestRenderer.create(element);
  });
  if (renderer === undefined) throw new Error("Renderer did not mount");
  return renderer;
}

function flattenStyle(style: unknown): Record<string, unknown> {
  const resolved = typeof style === "function" ? style({ pressed: false }) : style;
  const values = Array.isArray(resolved) ? resolved.flat(Infinity) : [resolved];
  return Object.assign({}, ...values.filter((value): value is Record<string, unknown> => (
    typeof value === "object" && value !== null
  )));
}

function findHostByProps(renderer: ReactTestRenderer, props: Record<string, unknown>) {
  const match = renderer.root.findAll((node) => (
    typeof node.type === "string"
    && Object.entries(props).every(([key, value]) => node.props[key] === value)
  ))[0];
  if (match === undefined) throw new Error("Host element not found");
  return match;
}

test("renders compact page headings with optional opposite action in RTL and LTR", () => {
  const action = createElement(
    "Pressable",
    { accessibilityLabel: "ویرایش", accessibilityRole: "button" },
    createElement("Text", null, "ویرایش"),
  );

  const rtlRenderer = render(
    createElement(PageHeading, {
      action,
      direction: "rtl",
      eyebrow: "امروز",
      supportingText: "خلاصه فعالیت شما",
      testID: "rtl-heading",
      title: "خانه",
    }),
  );

  expect(rtlRenderer.root.findByProps({ accessibilityRole: "header" }).props.children).toBe("خانه");
  expect(rtlRenderer.root.findByProps({ accessibilityLabel: "ویرایش" })).toBeTruthy();
  expect(flattenStyle(findHostByProps(rtlRenderer, { testID: "rtl-heading" }).props.style)).toMatchObject({
    direction: "rtl",
    flexDirection: "row",
  });
  expect(flattenStyle(findHostByProps(rtlRenderer, { children: "خانه" }).parent?.props.style)).toMatchObject({
    alignItems: "stretch",
  });

  const ltrRenderer = render(
    createElement(PageHeading, {
      direction: "ltr",
      testID: "ltr-heading",
      title: "Workout",
    }),
  );

  expect(ltrRenderer.root.findByProps({ accessibilityRole: "header" }).props.children).toBe("Workout");
  expect(flattenStyle(findHostByProps(ltrRenderer, { testID: "ltr-heading" }).props.style)).toMatchObject({
    direction: "ltr",
    flexDirection: "row",
  });
});

test("renders a selected RTL segmented option with a 48dp interaction target", () => {
  const onChange = vi.fn();
  const renderer = render(
    createElement(SegmentedControl, {
      accessibilityLabel: "نوع برنامه",
      onChange,
      options: [
        { label: "برنامه", value: "plan" },
        { label: "دستی", value: "manual" },
      ],
      selectedValue: "plan",
    }),
  );

  const selected = renderer.root.findByProps({ accessibilityLabel: "برنامه" });
  expect(selected.props.accessibilityRole).toBe("radio");
  expect(selected.props.accessibilityState).toMatchObject({ disabled: false, selected: true });
  expect(flattenStyle(selected.props.style)).toMatchObject({ minHeight: 48, minWidth: 48 });
  expect(flattenStyle(renderer.root.findByProps({ testID: "segmented-control" }).props.style)).toMatchObject({
    direction: "rtl",
    flexDirection: "row",
  });

  act(() => {
    renderer.root.findByProps({ accessibilityLabel: "دستی" }).props.onPress();
  });
  expect(onChange).toHaveBeenCalledWith("manual");
});

test("keeps grouped-list rows full-width and pressable", () => {
  const onPress = vi.fn();
  const renderer = render(
    createElement(GroupedList, {
      sections: [
        {
          items: [{ label: "تنظیمات", onPress }],
          title: "حساب کاربری",
        },
      ],
    }),
  );

  const row = renderer.root.findByProps({ accessibilityLabel: "تنظیمات" });
  expect(row.props.accessibilityRole).toBe("button");
  const rowStyle = flattenStyle(row.props.style);
  expect(rowStyle.width).toBe("100%");
  expect(rowStyle.minHeight).toBeGreaterThanOrEqual(48);
  expect(rowStyle.flexDirection).toBe("row");
  expect(flattenStyle(findHostByProps(renderer, { children: "تنظیمات" }).parent?.props.style)).toMatchObject({
    alignItems: "stretch",
  });
  act(() => row.props.onPress());
  expect(onPress).toHaveBeenCalledTimes(1);
});

test("keeps shared Persian headers and disclosure copy on the logical RTL side", () => {
  const sectionRenderer = render(
    createElement(SectionHeader, { title: "تنظیمات", actionLabel: "ویرایش", onAction: vi.fn() }),
  );
  const sectionViews = sectionRenderer.root.findAll((node) => String(node.type) === "View");
  expect(flattenStyle(sectionViews[0]?.props.style).flexDirection).toBe("row");
  expect(flattenStyle(findHostByProps(sectionRenderer, { children: "تنظیمات" }).parent?.props.style)).toMatchObject({
    alignItems: "stretch",
  });

  const screenRenderer = render(
    createElement(ScreenHeader, { subtitle: "توضیحات فارسی", title: "داشبورد" }),
  );
  const screenViews = screenRenderer.root.findAll((node) => String(node.type) === "View");
  expect(flattenStyle(screenViews[2]?.props.style).alignItems).toBe("stretch");

  const disclosureRenderer = render(
    createElement(DisclosureCard, { summary: "خلاصه فارسی", title: "جزئیات", children: "محتوا" }),
  );
  const disclosureHeader = disclosureRenderer.root.find((node) => String(node.type) === "Pressable");
  expect(flattenStyle(disclosureHeader.props.style).flexDirection).toBe("row");
  expect(flattenStyle(findHostByProps(disclosureRenderer, { children: "جزئیات" }).parent?.props.style)).toMatchObject({
    alignItems: "stretch",
  });
});

test("renders a page heading without inventing a brand row", () => {
  const renderer = render(createElement(PageHeading, { title: "پروفایل" }));

  expect(renderer.root.findByProps({ accessibilityRole: "header" }).props.children).toBe("پروفایل");
  expect(renderer.root.findAllByProps({ children: "FITICIAN" })).toHaveLength(0);
  expect(renderer.root.findAllByProps({ accessibilityRole: "button" })).toHaveLength(0);
});

test("keeps segmented controls disabled while loading", () => {
  const renderer = render(
    createElement(SegmentedControl, {
      loading: true,
      onChange: vi.fn(),
      options: [{ label: "فعال", value: "active" }],
      selectedValue: "active",
    }),
  );

  const option = renderer.root.findByProps({ accessibilityLabel: "فعال" });
  expect(option.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
  expect(option.props.disabled).toBe(true);
});
