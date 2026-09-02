import { StrictMode } from "react";
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

it("changes only the Ghost size while keeping the photo framing fixed", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const ghost = screen.getByRole("img", { name: /loose front body-position silhouette/i });
  const initialImageTransform = image.style.transform;

  fireEvent.click(screen.getByRole("button", { name: /make ghost smaller/i }));

  expect(ghost).toHaveStyle({ transform: "scale(0.95)" });
  expect(image.style.transform).toBe(initialImageTransform);
});

it("shows the left side Ghost without changing photo framing", () => {
  const { container } = render(
    <GhostPhotoEditor
      file={sourceFile}
      view="side"
      sideProfile="left"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      renderPhoto={renderPhoto}
    />,
  );

  expect(container.querySelector(".ghost-overlay__asset-frame")).toHaveStyle({
    transform: "scaleX(-1) scale(1)",
  });
});

it("allows a quarter-turn through the rotation slider", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const rotationSlider = screen.getByRole("slider", { name: /rotation/i });

  expect(rotationSlider).toHaveAttribute("min", "-180");
  expect(rotationSlider).toHaveAttribute("max", "180");

  fireEvent.change(rotationSlider, { target: { value: "90" } });

  expect(image.style.transform).toContain("rotate(90deg)");
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

it("uses two active pointers to pinch-zoom and rotate the photo", () => {
  renderEditor();
  const stage = screen.getByRole("application", { name: /photo framing editor/i });
  const image = screen.getByRole("img", { name: /photo being aligned/i });

  fireEvent.pointerDown(stage, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerDown(stage, { pointerId: 2, clientX: 200, clientY: 100 });
  fireEvent.pointerMove(stage, { pointerId: 1, clientX: 95, clientY: 95 });
  fireEvent.pointerMove(stage, { pointerId: 2, clientX: 205, clientY: 105 });

  expect(image.style.transform).toContain("translate(0px, 0px)");
  expect(image.style.transform).toContain("rotate(5.194deg)");
  expect(image.style.transform).toContain("scale(1.105)");
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
    "front",
  ));
  expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ type: "image/jpeg" }));
});

it("passes the back view to the clean renderer", async () => {
  render(
    <GhostPhotoEditor
      file={sourceFile}
      view="back"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      renderPhoto={renderPhoto}
    />,
  );

  await fireEvent.click(screen.getByRole("button", { name: /use this photo/i }));

  await waitFor(() => expect(renderPhoto).toHaveBeenCalledWith(
    sourceFile,
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    "back",
  ));
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

it("keeps the live preview URL usable under React StrictMode", () => {
  vi.mocked(URL.createObjectURL)
    .mockReset()
    .mockReturnValueOnce("blob:strict-first")
    .mockReturnValue("blob:strict-live");

  render(
    <StrictMode>
      <GhostPhotoEditor
        file={sourceFile}
        view="front"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        renderPhoto={renderPhoto}
      />
    </StrictMode>,
  );

  expect(screen.getByRole("img", { name: /photo being aligned/i })).toHaveAttribute("src", "blob:strict-live");
  expect(URL.revokeObjectURL).not.toHaveBeenCalledWith("blob:strict-live");
});
