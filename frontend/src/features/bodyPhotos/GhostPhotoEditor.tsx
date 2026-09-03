import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Sex } from "../profile/types";
import { GhostOverlayGuide } from "./GhostOverlayGuide";
import { GhostScaleControls } from "./GhostScaleControls";
import { GHOST_SCALE_MAX, GHOST_SCALE_MIN } from "./ghostScale";
import {
  clampGhostPhotoTransform,
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  isGhostFramingWithinTolerance,
  renderGhostPhoto,
} from "./ghostPhotoEditor";
import type { BodyPhotoSide, BodyPhotoView, GhostTransform } from "./types";

export type GhostPhotoRenderer = (
  file: File,
  transform: GhostTransform,
  view: BodyPhotoView,
) => Promise<File>;

type GhostPhotoEditorProps = {
  file: File;
  sex?: Sex | null;
  sideProfile?: BodyPhotoSide;
  view: BodyPhotoView;
  onConfirm: (file: File) => void | Promise<void>;
  onCancel: () => void;
  renderPhoto?: GhostPhotoRenderer;
};

type DragState = {
  pointerId: number;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
  stageWidth: number;
  stageHeight: number;
};

type GhostPhotoPoint = {
  x: number;
  y: number;
};

type PinchGesture = {
  initialCenter: GhostPhotoPoint;
  initialDistance: number;
  initialAngle: number;
  initialTransform: GhostTransform;
  stageWidth: number;
  stageHeight: number;
};

const zoomStep = 0.1;
const rotationStep = 1;

export function GhostPhotoEditor({
  file,
  sex,
  sideProfile,
  view,
  onConfirm,
  onCancel,
  renderPhoto = renderGhostPhoto,
}: GhostPhotoEditorProps) {
  const { t } = useTranslation();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const pointersRef = useRef(new Map<number, GhostPhotoPoint>());
  const pinchRef = useRef<PinchGesture | null>(null);
  const [transform, setTransform] = useState<GhostTransform>(GHOST_EDITOR_DEFAULT_TRANSFORM);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const nextPreviewUrl = URL.createObjectURL(file);
    setPreviewUrl(nextPreviewUrl);
    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [file]);

  function updateTransform(update: (current: GhostTransform) => GhostTransform) {
    setTransform((current) => clampGhostPhotoTransform(update(current)));
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (confirming) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    const stageSize = getStageSize(event.currentTarget);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const points = firstTwoPointerPoints(pointersRef.current);
    if (pointersRef.current.size >= 2 && points !== null) {
      dragRef.current = null;
      pinchRef.current = createPinchGesture(points[0], points[1], transform, stageSize);
      return;
    }
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: transform.translateX,
      originY: transform.translateY,
      stageWidth: stageSize.width,
      stageHeight: stageSize.height,
    };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const pointers = pointersRef.current;
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pinch = pinchRef.current;
    const points = firstTwoPointerPoints(pointers);
    if (pinch !== null && points !== null) {
      event.preventDefault();
      setTransform(clampGhostPhotoTransform(applyPinchGesture(pinch, points[0], points[1])));
      return;
    }
    const drag = dragRef.current;
    if (drag === null || drag.pointerId !== event.pointerId) return;
    updateTransform((current) => ({
      ...current,
      translateX: drag.originX + (event.clientX - drag.startX) / drag.stageWidth,
      translateY: drag.originY + (event.clientY - drag.startY) / drag.stageHeight,
    }));
  }

  function finishPointerDrag(event: React.PointerEvent<HTMLDivElement>) {
    pointersRef.current.delete(event.pointerId);
    pinchRef.current = null;
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null;
    const remaining = Array.from(pointersRef.current.entries())[0];
    if (remaining !== undefined) {
      const [pointerId, point] = remaining;
      const stageSize = getStageSize(event.currentTarget);
      dragRef.current = {
        pointerId,
        startX: point.x,
        startY: point.y,
        originX: transform.translateX,
        originY: transform.translateY,
        stageWidth: stageSize.width,
        stageHeight: stageSize.height,
      };
    }
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }

  function confirm() {
    if (confirming) return;
    setConfirming(true);
    setError(null);
    void renderPhoto(file, transform, view)
      .then((editedFile) => onConfirm(editedFile))
      .catch(() => setError(t("bodyPhotos.editor.renderError")))
      .finally(() => setConfirming(false));
  }

  const framingIsWithinTolerance = isGhostFramingWithinTolerance(transform);

  return (
    <section className="ghost-photo-editor" aria-labelledby="ghost-photo-editor-title">
      <header className="ghost-photo-editor__heading">
        <p className="eyebrow eyebrow--accent">{t("bodyPhotos.editor.eyebrow")}</p>
        <h3 id="ghost-photo-editor-title">{t("bodyPhotos.editor.title")}</h3>
        <p>{t("bodyPhotos.editor.body")}</p>
      </header>
      <div
        className="ghost-photo-editor__stage"
        role="application"
        aria-label={t("bodyPhotos.editor.stageLabel")}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={finishPointerDrag}
        onPointerCancel={finishPointerDrag}
      >
        {previewUrl !== null && (
          <img
            className="ghost-photo-editor__image"
            src={previewUrl}
            alt={t("bodyPhotos.editor.imageAlt", { view: t(`bodyPhotos.views.${view}`) })}
            draggable={false}
            style={{ transform: "translate(-50%, -50%)" }}
          />
        )}
        <GhostOverlayGuide sex={sex} transform={transform} sideProfile={sideProfile} view={view} />
      </div>
      <p className="ghost-photo-editor__privacy-note">{t("bodyPhotos.editor.privacyNote")}</p>
      <p className="ghost-photo-editor__status" role="status">
        {framingIsWithinTolerance
          ? t("bodyPhotos.editor.framingOkay")
          : t("bodyPhotos.editor.framingApproximate")}
      </p>
      <div className="ghost-photo-editor__controls" aria-label={t("bodyPhotos.editor.controlsLabel")}>
        <GhostScaleControls
          disabled={confirming}
          onScaleChange={(scale) => updateTransform((current) => ({ ...current, scale }))}
          scale={transform.scale}
        />
        <div className="ghost-photo-editor__button-row">
          <button
            className="secondary-button"
            type="button"
            onClick={() => updateTransform((current) => ({ ...current, scale: current.scale - zoomStep }))}
            disabled={confirming}
          >
            {t("bodyPhotos.editor.zoomOut")}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => updateTransform((current) => ({ ...current, scale: current.scale + zoomStep }))}
            disabled={confirming}
          >
            {t("bodyPhotos.editor.zoomIn")}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => updateTransform((current) => ({ ...current, rotation: current.rotation - rotationStep }))}
            disabled={confirming}
          >
            {t("bodyPhotos.editor.rotateLeft")}
          </button>
          <button
            className="secondary-button"
            type="button"
            onClick={() => updateTransform((current) => ({ ...current, rotation: current.rotation + rotationStep }))}
            disabled={confirming}
          >
            {t("bodyPhotos.editor.rotateRight")}
          </button>
        </div>
        <label className="ghost-photo-editor__range">
          <span>{t("bodyPhotos.editor.zoomLabel")}</span>
          <input
            type="range"
            min={String(GHOST_SCALE_MIN)}
            max={String(GHOST_SCALE_MAX)}
            step="0.05"
            value={transform.scale}
            aria-label={t("bodyPhotos.editor.zoomLabel")}
            onChange={(event) => updateTransform((current) => ({ ...current, scale: Number(event.target.value) }))}
            disabled={confirming}
          />
        </label>
        <label className="ghost-photo-editor__range">
          <span>{t("bodyPhotos.editor.rotationLabel")}</span>
          <input
            type="range"
            min="-180"
            max="180"
            step="1"
            value={transform.rotation}
            aria-label={t("bodyPhotos.editor.rotationLabel")}
            onChange={(event) => updateTransform((current) => ({ ...current, rotation: Number(event.target.value) }))}
            disabled={confirming}
          />
        </label>
        <button
          className="body-photo-link-button"
          type="button"
          onClick={() => setTransform(GHOST_EDITOR_DEFAULT_TRANSFORM)}
          disabled={confirming}
        >
          {t("bodyPhotos.editor.reset")}
        </button>
      </div>
      {error !== null && <p className="form-error" role="alert">{error}</p>}
      <div className="ghost-photo-editor__actions">
        <button className="secondary-button" type="button" onClick={onCancel} disabled={confirming}>
          {t("bodyPhotos.editor.cancel")}
        </button>
        <button className="primary-button" type="button" onClick={confirm} disabled={confirming}>
          {confirming ? t("bodyPhotos.editor.confirming") : t("bodyPhotos.editor.confirm")}
        </button>
      </div>
    </section>
  );
}

function firstTwoPointerPoints(
  pointers: Map<number, GhostPhotoPoint>,
): [GhostPhotoPoint, GhostPhotoPoint] | null {
  const points = Array.from(pointers.values());
  if (points.length < 2) return null;
  return [points[0]!, points[1]!];
}

function createPinchGesture(
  first: GhostPhotoPoint,
  second: GhostPhotoPoint,
  transform: GhostTransform,
  stageSize: StageSize,
): PinchGesture {
  return {
    initialCenter: midpoint(first, second),
    initialDistance: distance(first, second),
    initialAngle: angle(first, second),
    initialTransform: transform,
    stageWidth: stageSize.width,
    stageHeight: stageSize.height,
  };
}

function applyPinchGesture(
  gesture: PinchGesture,
  first: GhostPhotoPoint,
  second: GhostPhotoPoint,
): GhostTransform {
  const currentCenter = midpoint(first, second);
  const initialDistance = gesture.initialDistance;
  const scaleRatio = initialDistance === 0 ? 1 : distance(first, second) / initialDistance;
  const rotationDelta = shortestAngleDelta(angle(first, second) - gesture.initialAngle);
  return {
    translateX: gesture.initialTransform.translateX
      + (currentCenter.x - gesture.initialCenter.x) / gesture.stageWidth,
    translateY: gesture.initialTransform.translateY
      + (currentCenter.y - gesture.initialCenter.y) / gesture.stageHeight,
    scale: gesture.initialTransform.scale * scaleRatio,
    rotation: gesture.initialTransform.rotation + (rotationDelta * 180) / Math.PI,
  };
}

type StageSize = {
  width: number;
  height: number;
};

function getStageSize(element: HTMLElement): StageSize {
  const rect = element.getBoundingClientRect();
  return {
    width: rect.width > 0 ? rect.width : GHOST_EDITOR_OUTPUT.width,
    height: rect.height > 0 ? rect.height : GHOST_EDITOR_OUTPUT.height,
  };
}

function midpoint(first: GhostPhotoPoint, second: GhostPhotoPoint): GhostPhotoPoint {
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function distance(first: GhostPhotoPoint, second: GhostPhotoPoint): number {
  return Math.hypot(second.x - first.x, second.y - first.y);
}

function angle(first: GhostPhotoPoint, second: GhostPhotoPoint): number {
  return Math.atan2(second.y - first.y, second.x - first.x);
}

function shortestAngleDelta(delta: number): number {
  if (delta > Math.PI) return delta - 2 * Math.PI;
  if (delta < -Math.PI) return delta + 2 * Math.PI;
  return delta;
}
