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

export function pendingLocalBodyPhotoViews(
  session: BodyPhotoSession,
  localViews: Iterable<BodyPhotoView>,
): BodyPhotoView[] {
  const uploadedViews = new Set(session.photos.map((photo) => photo.view));
  const localViewSet = new Set(localViews);
  return ( ["front", "side", "back"] as const).filter((view) => (
    localViewSet.has(view) && !uploadedViews.has(view)
  ));
}

export function draftForCapturedBodyPhoto(
  draft: BodyPhotoFlowDraft,
  view: BodyPhotoView,
  nextView: BodyPhotoView | null,
): BodyPhotoFlowDraft {
  return {
    ...draft,
    capture_mode: "library",
    current_view: nextView ?? view,
    updated_at: Date.now(),
  };
}
