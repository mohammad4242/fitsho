import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  ghostPhotoTransformStyle,
} from "./ghostPhotoEditor";
import {
  type GhostPhotoRenderer,
} from "./GhostPhotoEditor";
import { GhostPhotoEditor } from "./GhostPhotoEditor";
import type { BodyPhotoView } from "./types";

const sourceFile = new File(["source"], "side.png", { type: "image/png" });

const renderPhoto: GhostPhotoRenderer = vi.fn(async () => (
  new File(["clean"], "body-photo-edited.jpg", { type: "image/jpeg" })
));

function renderEditor(view: BodyPhotoView = "front") {
  return render(
    <GhostPhotoEditor
      file={sourceFile}
      view={view}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      renderPhoto={renderPhoto}
    />,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:editor-source");
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
});

it.each(["front", "side", "back"] as const)("renders the %s Ghost guide over the editable image", (view) => {
  renderEditor(view);

  expect(screen.getByRole("heading", { name: /align your photo/i })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: new RegExp(`loose ${view} body-position silhouette`, "i") })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /photo being aligned/i }).style.transform).toBe(
    ghostPhotoTransformStyle(GHOST_EDITOR_DEFAULT_TRANSFORM),
  );
});

it("supports keyboard-accessible zoom, rotation, and reset controls", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });

  fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
  expect(image.style.transform).toContain("scale(1.1)");

  fireEvent.click(screen.getByRole("button", { name: /rotate right/i }));
  expect(image.style.transform).toContain("rotate(1deg)");

  fireEvent.click(screen.getByRole("button", { name: /reset framing/i }));
  expect(image.style.transform).toBe(ghostPhotoTransformStyle(GHOST_EDITOR_DEFAULT_TRANSFORM));
});

it("moves the image with a pointer drag and reports the soft framing status", () => {
  renderEditor();
  const stage = screen.getByRole("application", { name: /photo framing editor/i });
  const image = screen.getByRole("img", { name: /photo being aligned/i });

  fireEvent.pointerDown(stage, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(stage, { pointerId: 1, clientX: 180, clientY: 160 });
  fireEvent.pointerUp(stage, { pointerId: 1, clientX: 180, clientY: 160 });

  expect(image.style.transform).toContain("translate(80px, 60px)");
  expect(screen.getByRole("status")).toHaveTextContent(/approximate framing is okay/i);
});

it("returns the clean rendered file only after confirmation", async () => {
  const onConfirm = vi.fn();
  render(
    <GhostPhotoEditor
      file={sourceFile}
      view="front"
      onConfirm={onConfirm}
      onCancel={vi.fn()}
      renderPhoto={renderPhoto}
    />,
  );

  await fireEvent.click(screen.getByRole("button", { name: /use this photo/i }));

  await waitFor(() => expect(renderPhoto).toHaveBeenCalledWith(
    sourceFile,
    GHOST_EDITOR_DEFAULT_TRANSFORM,
  ));
  expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ type: "image/jpeg" }));
});

it("cancels without rendering or confirming", () => {
  const onCancel = vi.fn();
  render(
    <GhostPhotoEditor
      file={sourceFile}
      view="back"
      onConfirm={vi.fn()}
      onCancel={onCancel}
      renderPhoto={renderPhoto}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /cancel editing/i }));

  expect(onCancel).toHaveBeenCalledOnce();
  expect(renderPhoto).not.toHaveBeenCalled();
});

it("releases its source preview URL when it unmounts", () => {
  const rendered = renderEditor();

  rendered.unmount();

  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:editor-source");
});
