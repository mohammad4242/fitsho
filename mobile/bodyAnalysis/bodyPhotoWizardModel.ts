import type {
  BodyPhotoPurpose,
  BodyPhotoSession,
  BodyPhotoView,
} from "@fitician/core/body-photos";

import {
  firstMissingBodyPhotoViewFromViews,
  type BodyPhotoFlowDraft,
} from "./bodyPhotoFlow";

export function bodyPhotoPurposeFromParam(value: string | undefined): BodyPhotoPurpose {
  if (value === "cycle_completion" || value === "progress_check") return value;
  return "initial_plan";
}

export function isResumableBodyPhotoSession(session: BodyPhotoSession): boolean {
  return session.state === "draft"
    || session.state === "awaiting_consent"
    || session.state === "uploading"
    || session.state === "uploaded"
    || session.state === "failed";
}

export function nextLocalBodyPhotoView(
  session: BodyPhotoSession,
  localViews: Iterable<BodyPhotoView>,
  capturedView: BodyPhotoView,
): BodyPhotoView | null {
  return firstMissingBodyPhotoViewFromViews([
    ...session.photos.map((photo) => photo.view),
    ...localViews,
    capturedView,
  ]);
}

export function draftForCapturedBodyPhoto(
  draft: BodyPhotoFlowDraft,
  view: BodyPhotoView,
  nextView: BodyPhotoView | null,
  captureMode: BodyPhotoFlowDraft["capture_mode"],
): BodyPhotoFlowDraft {
  return {
    ...draft,
    capture_mode: captureMode,
    current_view: nextView ?? view,
    updated_at: Date.now(),
  };
}
