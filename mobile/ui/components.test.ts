import { expect, it, vi } from "vitest";
import { type ReactNode } from "react";

type NativeElement = {
  readonly type: string;
  readonly props: Record<string, unknown>;
};

const native = vi.hoisted(() => {
  const primitive = (type: string) => (props: Record<string, unknown>) => ({ type, props });
  return {
    ActivityIndicator: primitive("ActivityIndicator"),
    Image: primitive("Image"),
    Modal: primitive("Modal"),
    Pressable: primitive("Pressable"),
    ScrollView: primitive("ScrollView"),
    Text: primitive("Text"),
    TextInput: primitive("TextInput"),
    View: primitive("View"),
    play: vi.fn(),
  };
});

vi.mock("react-native", () => ({
  ...native,
  StyleSheet: {
    absoluteFill: { bottom: 0, left: 0, position: "absolute", right: 0, top: 0 },
    create: <T extends Record<string, unknown>>(styles: T): T => styles,
  },
}));

vi.mock("expo-video", () => ({
  useVideoPlayer: (
    _source: unknown,
    setup?: (player: { loop: boolean; muted: boolean; play: () => void }) => void,
  ) => {
    const player = { loop: false, muted: false, play: native.play };
    setup?.(player);
    return player;
  },
  VideoView: native.View,
}));

vi.mock("react-native-safe-area-context", () => ({ SafeAreaView: native.View }));

import { Button } from "./components/Button";
import { Card } from "./components/Card";
import { Dialog, Sheet } from "./components/Overlay";
import { FormField, TextField } from "./components/Input";
import { Media } from "./components/Media";
import { Notice, Skeleton } from "./components/Feedback";

function element(value: unknown): NativeElement {
  let current = value as { type: unknown; props: Record<string, unknown> };
  while (typeof current.type === "function") {
    current = current.type(current.props) as typeof current;
  }
  expect(current).toMatchObject({ type: expect.any(String), props: expect.any(Object) });
  return current as NativeElement;
}

it("renders token-based button variants and exposes busy state", () => {
  const result = element(
    Button({ label: "Save", loading: true, variant: "primary", onPress: vi.fn() }),
  );

  expect(result.type).toBe("Pressable");
  expect(result.props.accessibilityRole).toBe("button");
  expect(result.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
  expect(result.props.disabled).toBe(true);
  expect(element(result.props.children).type).toBe("ActivityIndicator");

  const style = (result.props.style as (state: { pressed: boolean }) => unknown)({ pressed: false });
  expect(style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: "#50dfce" })]));
});

it("renders fields through a shared form-field shell with error feedback", () => {
  const result = element(
    TextField({ label: "Email", error: "Invalid email", value: "bad", onChangeText: vi.fn() }),
  );
  const shell = result;
  const children = shell.props.children as readonly unknown[];

  expect(shell.type).toBe("View");
  expect(element(children[0]).type).toBe("Text");
  expect(element(children[1]).type).toBe("TextInput");
  expect(element(children[2]).props.children).toBe("Invalid email");
  expect(element(children[1]).props.accessibilityHint).toBe("Invalid email");
});

it("supports reusable form-field content around non-text controls", () => {
  const result = element(
    FormField({
      description: "Optional",
      label: "Goal",
      children: native.View({}) as unknown as ReactNode,
    }),
  );
  const children = result.props.children as readonly unknown[];

  expect(result.type).toBe("View");
  expect(element(children[0]).props.children).toContain("Goal");
  expect(element(children[1]).type).toBe("View");
  expect(element(children[2]).props.children).toBe("Optional");
});

it("uses a pressable card only when the card is interactive", () => {
  const interactive = element(Card({ onPress: vi.fn(), variant: "interactive", children: "Plan" }));
  const staticCard = element(Card({ children: "Plan" }));

  expect(interactive.type).toBe("Pressable");
  expect(interactive.props.accessibilityRole).toBe("button");
  expect(staticCard.type).toBe("View");
});

it("keeps sheet and dialog overlays native and dismissible", () => {
  const onClose = vi.fn();
  const sheet = element(Sheet({ title: "Details", visible: true, onClose, children: "Body" }));
  const dialog = element(
    Dialog({
      message: "Delete this item?",
      onClose,
      onConfirm: vi.fn(),
      title: "Confirm",
      visible: true,
    }),
  );

  expect(sheet.type).toBe("Modal");
  expect(sheet.props.animationType).toBe("slide");
  expect(sheet.props.onRequestClose).toBe(onClose);
  expect(dialog.type).toBe("Modal");
  expect(dialog.props.animationType).toBe("fade");
  expect(dialog.props.onRequestClose).toBe(onClose);
});

it("provides skeleton, notices, and native image/video media", () => {
  const skeleton = element(Skeleton({ height: 24, width: "100%" }));
  const notice = element(Notice({ message: "Offline", title: "Connection", variant: "offline" }));
  const image = element(Media({ source: { uri: "https://example.test/image.jpg" } }));
  const video = element(Media({ kind: "video", source: "https://example.test/video.mp4", autoplay: true }));

  expect(skeleton.type).toBe("View");
  expect(notice.type).toBe("View");
  expect(image.type).toBe("Image");
  expect(video.type).toBe("View");
  expect(native.play).toHaveBeenCalledOnce();
});
