import { StrictMode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  ghostGuideTransformStyle,
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
const staticGhostScale = 1;

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

it("supports keyboard-accessible photo zoom, rotation, and reset controls without moving Ghost", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const ghost = screen.getByRole("img", { name: /loose front body-position silhouette/i });

  fireEvent.click(screen.getByRole("button", { name: /zoom in/i }));
  expect(image).toHaveStyle({
    transform: ghostPhotoTransformStyle({ ...GHOST_EDITOR_DEFAULT_TRANSFORM, scale: 1.1 }),
  });
  expect(ghost).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });

  fireEvent.click(screen.getByRole("button", { name: /rotate right/i }));
  expect(image).toHaveStyle({
    transform: ghostPhotoTransformStyle({ ...GHOST_EDITOR_DEFAULT_TRANSFORM, scale: 1.1, rotation: 1 }),
  });
  expect(ghost).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });

  fireEvent.click(screen.getByRole("button", { name: /reset framing/i }));
  expect(image).toHaveStyle({
    transform: ghostPhotoTransformStyle(GHOST_EDITOR_DEFAULT_TRANSFORM),
  });
  expect(ghost).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });
});

it("changes only the Ghost size while keeping the photo framing fixed", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const ghost = screen.getByRole("img", { name: /loose front body-position silhouette/i });
  const initialImageTransform = image.style.transform;

  fireEvent.click(screen.getByRole("button", { name: /make ghost smaller/i }));

  expect(ghost).toHaveStyle({
    transform: ghostGuideTransformStyle(0.95),
  });
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
    transform: ghostGuideTransformStyle(1, true),
  });
});

it("allows a quarter-turn through the rotation slider", () => {
  renderEditor();
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const ghost = screen.getByRole("img", { name: /loose front body-position silhouette/i });
  const rotationSlider = screen.getByRole("slider", { name: /rotation/i });

  expect(rotationSlider).toHaveAttribute("min", "-180");
  expect(rotationSlider).toHaveAttribute("max", "180");

  fireEvent.change(rotationSlider, { target: { value: "90" } });

  expect(image).toHaveStyle({
    transform: ghostPhotoTransformStyle({ ...GHOST_EDITOR_DEFAULT_TRANSFORM, rotation: 90 }),
  });
  expect(ghost).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });
});

it("moves the photo with a pointer drag while keeping Ghost fixed", () => {
  renderEditor();
  const stage = screen.getByRole("application", { name: /photo framing editor/i });
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const frame = stage.querySelector<HTMLElement>(".ghost-overlay__asset-frame");
  expect(frame).not.toBeNull();
  if (frame === null) throw new Error("Ghost frame was not rendered");
  vi.spyOn(stage, "getBoundingClientRect").mockReturnValue({
    width: 300,
    height: 450,
  } as DOMRect);

  fireEvent.pointerDown(stage, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerMove(stage, { pointerId: 1, clientX: 180, clientY: 160 });
  fireEvent.pointerUp(stage, { pointerId: 1, clientX: 180, clientY: 160 });

  expect(image).toHaveStyle({
    transform: ghostPhotoTransformStyle({
      ...GHOST_EDITOR_DEFAULT_TRANSFORM,
      translateX: 80 / 300,
      translateY: 60 / 450,
    }),
  });
  expect(frame).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });
  expect(screen.getByRole("status")).toHaveTextContent(/move the photo closer/i);
});

it.each(["front", "side", "back"] as const)("uses two active pointers to pinch-zoom and rotate the %s photo", (view) => {
  renderEditor(view);
  const stage = screen.getByRole("application", { name: /photo framing editor/i });
  const image = screen.getByRole("img", { name: /photo being aligned/i });
  const frame = stage.querySelector<HTMLElement>(".ghost-overlay__asset-frame");
  expect(frame).not.toBeNull();
  if (frame === null) throw new Error("Ghost frame was not rendered");
  vi.spyOn(stage, "getBoundingClientRect").mockReturnValue({
    width: 300,
    height: 450,
  } as DOMRect);

  fireEvent.pointerDown(stage, { pointerId: 1, clientX: 100, clientY: 100 });
  fireEvent.pointerDown(stage, { pointerId: 2, clientX: 200, clientY: 100 });
  fireEvent.pointerMove(stage, { pointerId: 1, clientX: 95, clientY: 95 });
  fireEvent.pointerMove(stage, { pointerId: 2, clientX: 205, clientY: 105 });

  expect(image.style.transform).toContain("translate(0%, 0%)");
  expect(image.style.transform).toContain("rotate(5.194deg)");
  expect(image.style.transform).toContain("scale(1.105)");
  expect(frame).toHaveStyle({ transform: ghostGuideTransformStyle(staticGhostScale) });
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
    staticGhostScale,
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
    staticGhostScale,
  ));
});

it("passes the independent Ghost size to the crop renderer", async () => {
  renderEditor();

  fireEvent.click(screen.getByRole("button", { name: /make ghost smaller/i }));
  await fireEvent.click(screen.getByRole("button", { name: /use this photo/i }));

  await waitFor(() => expect(renderPhoto).toHaveBeenCalledWith(
    sourceFile,
    GHOST_EDITOR_DEFAULT_TRANSFORM,
    "front",
    0.95,
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
