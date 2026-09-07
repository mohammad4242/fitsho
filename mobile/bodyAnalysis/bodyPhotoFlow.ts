import {
  clampGhostScale,
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
} from "@fitician/core/body-ghost";
import type {
  BodyPhotoPurpose,
  BodyPhotoSession,
  BodyPhotoSide,
  BodyPhotoView,
} from "@fitician/core/body-photos";

export const BODY_PHOTO_FLOW_SCHEMA_VERSION = 1 as const;
export const BODY_PHOTO_VIEWS = ["front", "side", "back"] as const satisfies readonly BodyPhotoView[];

export type BodyPhotoFlowStage = "measurements" | "capture";
export type BodyPhotoCaptureMode = "camera" | "library";

export type BodyPhotoFlowDraft = {
  readonly capture_mode: BodyPhotoCaptureMode;
  readonly current_view: BodyPhotoView | null;
  readonly ghost_scale: number;
  readonly purpose: BodyPhotoPurpose;
  readonly schema_version: typeof BODY_PHOTO_FLOW_SCHEMA_VERSION;
  readonly session_id: string | null;
  readonly side_profile: BodyPhotoSide;
  readonly stage: BodyPhotoFlowStage;
  readonly updated_at: number;
};

export function firstMissingBodyPhotoView(session: BodyPhotoSession): BodyPhotoView | null {
  const uploadedViews = new Set(session.photos.map((photo) => photo.view));
  return BODY_PHOTO_VIEWS.find((view) => !uploadedViews.has(view)) ?? null;
}

export function createBodyPhotoFlowDraft(
  purpose: BodyPhotoPurpose,
  sessionId: string | null = null,
  session?: BodyPhotoSession,
): BodyPhotoFlowDraft {
  const activeSession = sessionId !== null && session?.id === sessionId ? session : undefined;
  return {
    capture_mode: "camera",
    current_view: activeSession === undefined
      ? "front"
      : firstMissingBodyPhotoView(activeSession),
    ghost_scale: 1,
    purpose,
    schema_version: BODY_PHOTO_FLOW_SCHEMA_VERSION,
    session_id: sessionId,
    side_profile: "right",
    stage: sessionId === null ? "measurements" : "capture",
    updated_at: Date.now(),
  };
}

export function reconcileBodyPhotoFlowDraft(
  draft: BodyPhotoFlowDraft,
  session: BodyPhotoSession,
): BodyPhotoFlowDraft {
  const base = draft.session_id === session.id
    ? draft
    : createBodyPhotoFlowDraft(session.purpose, session.id, session);
  return {
    ...base,
    current_view: firstMissingBodyPhotoView(session),
    session_id: session.id,
    stage: "capture",
    updated_at: Date.now(),
  };
}

export function serializeBodyPhotoFlowDraft(draft: BodyPhotoFlowDraft): string {
  return JSON.stringify(draft);
}

export function parseBodyPhotoFlowDraft(
  value: string,
  expectedSessionId?: string,
): BodyPhotoFlowDraft | null {
  try {
    const parsed: unknown = JSON.parse(value);
    if (!isRecord(parsed)) return null;
    if (parsed.schema_version !== BODY_PHOTO_FLOW_SCHEMA_VERSION) return null;
    if (expectedSessionId !== undefined && parsed.session_id !== expectedSessionId) return null;
    if (!isBodyPhotoPurpose(parsed.purpose)) return null;
    if (parsed.session_id !== null && !isSafeIdentifier(parsed.session_id)) return null;
    if (!isBodyPhotoViewOrNull(parsed.current_view)) return null;
    if (parsed.capture_mode !== "camera" && parsed.capture_mode !== "library") return null;
    if (parsed.side_profile !== "right" && parsed.side_profile !== "left") return null;
    if (parsed.stage !== "measurements" && parsed.stage !== "capture") return null;
    if (
      typeof parsed.ghost_scale !== "number"
      || !Number.isFinite(parsed.ghost_scale)
      || parsed.ghost_scale < GHOST_SCALE_MIN
      || parsed.ghost_scale > GHOST_SCALE_MAX
    ) return null;
    if (typeof parsed.updated_at !== "number" || !Number.isFinite(parsed.updated_at)) return null;
    return {
      capture_mode: parsed.capture_mode,
      current_view: parsed.current_view,
      ghost_scale: clampGhostScale(parsed.ghost_scale),
      purpose: parsed.purpose,
      schema_version: BODY_PHOTO_FLOW_SCHEMA_VERSION,
      session_id: parsed.session_id,
      side_profile: parsed.side_profile,
      stage: parsed.stage,
      updated_at: parsed.updated_at,
    };
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isBodyPhotoViewOrNull(value: unknown): value is BodyPhotoView | null {
  return value === null || BODY_PHOTO_VIEWS.includes(value as BodyPhotoView);
}

function isBodyPhotoPurpose(value: unknown): value is BodyPhotoPurpose {
  return value === "initial_plan" || value === "cycle_completion" || value === "progress_check";
}

function isSafeIdentifier(value: unknown): value is string {
  return typeof value === "string"
    && value.length > 0
    && value.length <= 200
    && !/[\u0000-\u001f\u007f\s]/u.test(value);
}
