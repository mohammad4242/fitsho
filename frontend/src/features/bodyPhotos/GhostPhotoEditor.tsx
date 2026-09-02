import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { GhostOverlayGuide } from "./GhostOverlayGuide";
import {
  clampGhostPhotoTransform,
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  ghostPhotoTransformStyle,
  isGhostFramingWithinTolerance,
  renderGhostPhoto,
  type GhostPhotoTransform,
} from "./ghostPhotoEditor";
import type { BodyPhotoView } from "./types";

export type GhostPhotoRenderer = (
  file: File,
  transform: GhostPhotoTransform,
) => Promise<File>;

type GhostPhotoEditorProps = {
  file: File;
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
};

const zoomStep = 0.1;
const rotationStep = 1;

export function GhostPhotoEditor({
  file,
  view,
  onConfirm,
  onCancel,
  renderPhoto = renderGhostPhoto,
}: GhostPhotoEditorProps) {
  const { t } = useTranslation();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [transform, setTransform] = useState<GhostPhotoTransform>(GHOST_EDITOR_DEFAULT_TRANSFORM);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const nextPreviewUrl = URL.createObjectURL(file);
    setPreviewUrl(nextPreviewUrl);
    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [file]);

  function updateTransform(update: (current: GhostPhotoTransform) => GhostPhotoTransform) {
    setTransform((current) => clampGhostPhotoTransform(update(current)));
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (confirming) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: transform.offsetX,
      originY: transform.offsetY,
    };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (drag === null || drag.pointerId !== event.pointerId) return;
    updateTransform((current) => ({
      ...current,
      offsetX: drag.originX + event.clientX - drag.startX,
      offsetY: drag.originY + event.clientY - drag.startY,
    }));
  }

  function finishPointerDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }

  function confirm() {
    if (confirming) return;
    setConfirming(true);
    setError(null);
    void renderPhoto(file, transform)
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
            style={{ transform: ghostPhotoTransformStyle(transform) }}
          />
        )}
        <GhostOverlayGuide view={view} />
      </div>
      <p className="ghost-photo-editor__privacy-note">{t("bodyPhotos.editor.privacyNote")}</p>
      <p className="ghost-photo-editor__status" role="status">
        {framingIsWithinTolerance
          ? t("bodyPhotos.editor.framingOkay")
          : t("bodyPhotos.editor.framingApproximate")}
      </p>
      <div className="ghost-photo-editor__controls" aria-label={t("bodyPhotos.editor.controlsLabel")}>
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
            min="0.75"
            max="2.5"
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
            min="-15"
            max="15"
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
