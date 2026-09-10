import { expect, it, vi } from "vitest";

type NativeElement = {
  readonly type: string;
  readonly props: Record<string, unknown>;
};

const native = vi.hoisted(() => {
  const primitive = (type: string) => (props: Record<string, unknown>) => ({ type, props });
  const dimensions = { height: 844, width: 390 };
  return {
    ActivityIndicator: primitive("ActivityIndicator"),
    KeyboardAvoidingView: primitive("KeyboardAvoidingView"),
    Platform: { OS: "android" },
    ScrollView: primitive("ScrollView"),
    SafeAreaView: primitive("SafeAreaView"),
    StyleSheet: {
      create: <T extends Record<string, unknown>>(styles: T): T => styles,
    },
    View: primitive("View"),
    dimensions,
    useWindowDimensions: () => dimensions,
  };
});

vi.mock("react-native", () => native);
vi.mock("react-native-safe-area-context", () => ({
  SafeAreaView: native.SafeAreaView,
  useSafeAreaInsets: () => ({ bottom: 24, left: 0, right: 0, top: 24 }),
}));

import { Screen } from "./layout/Screen";

function element(value: unknown): NativeElement {
  let current = value as { type: unknown; props: Record<string, unknown> };
  while (typeof current.type === "function") {
    current = current.type(current.props) as typeof current;
  }
  return current as NativeElement;
}

it("wraps scrollable content in safe-area and keyboard-aware native containers", () => {
  const safeArea = element(Screen({ children: "form" }));
  const keyboard = element(safeArea.props.children);
  const scroll = element(keyboard.props.children);

  expect(safeArea.type).toBe("SafeAreaView");
  expect(safeArea.props.edges).toEqual(["top", "bottom"]);
  expect(keyboard.type).toBe("KeyboardAvoidingView");
  expect(keyboard.props.behavior).toBe("height");
  expect(keyboard.props.keyboardVerticalOffset).toBe(24);
  expect(scroll.type).toBe("ScrollView");
  expect(scroll.props.keyboardShouldPersistTaps).toBe("handled");
});

it("uses tablet gutters and reading width for non-scroll content", () => {
  native.dimensions.width = 1024;
  native.dimensions.height = 768;

  const safeArea = element(Screen({ children: "content", contentWidth: "reading", scroll: false }));
  const keyboard = element(safeArea.props.children);
  const content = element(keyboard.props.children);
  const style = content.props.style as readonly unknown[];

  expect(content.type).toBe("View");
  expect(JSON.stringify(style)).toContain('"direction":"rtl"');
  expect(JSON.stringify(style)).toContain('"alignItems":"stretch"');
  expect(JSON.stringify(style)).toContain('"paddingHorizontal":32');
  expect(JSON.stringify(style)).toContain('"maxWidth":1088');
});
