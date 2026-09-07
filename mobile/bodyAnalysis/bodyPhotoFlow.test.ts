import { expect, it } from "vitest";

import type { BodyPhotoSession } from "@fitician/core/body-photos";

import {
  BODY_PHOTO_FLOW_SCHEMA_VERSION,
  createBodyPhotoFlowDraft,
  firstMissingBodyPhotoView,
  parseBodyPhotoFlowDraft,
  reconcileBodyPhotoFlowDraft,
  serializeBodyPhotoFlowDraft,
  type BodyPhotoFlowDraft,
} from "./bodyPhotoFlow";

function session(photos: BodyPhotoSession["photos"]): BodyPhotoSession {
  return {
    created_at: "2026-09-08T10:00:00Z",
    id: "session-1",
    model_training_consent: null,
    operational_processing_consent: null,
    photos,
    purpose: "initial_plan",
    state: "draft",
    submitted_at: null,
    updated_at: "2026-09-08T10:00:00Z",
  };
}

it("keeps the shared three-view order and finds the first missing view", () => {
  expect(firstMissingBodyPhotoView(session([]))).toBe("front");
  expect(firstMissingBodyPhotoView(session([{ view: "front" } as BodyPhotoSession["photos"][number]]))).toBe("side");
  expect(firstMissingBodyPhotoView(session([
    { view: "back" },
    { view: "front" },
  ] as BodyPhotoSession["photos"]))).toBe("side");
  expect(firstMissingBodyPhotoView(session([
    { view: "front" },
    { view: "side" },
    { view: "back" },
  ] as BodyPhotoSession["photos"]))).toBeNull();
});

it("creates a resumable draft without persisting photo bytes or paths", () => {
  const draft = createBodyPhotoFlowDraft("initial_plan", "session-1");

  expect(draft).toEqual({
    capture_mode: "camera",
    current_view: "front",
    ghost_scale: 1,
    purpose: "initial_plan",
    schema_version: BODY_PHOTO_FLOW_SCHEMA_VERSION,
    session_id: "session-1",
    side_profile: "right",
    stage: "capture",
    updated_at: expect.any(Number),
  });
  expect(JSON.stringify(draft)).not.toMatch(/uri|bytes|base64|pixels/i);
});

it("reconciles a persisted draft with the server session after process death", () => {
  const draft: BodyPhotoFlowDraft = {
    capture_mode: "library",
    current_view: "front",
    ghost_scale: 0.9,
    purpose: "initial_plan",
    schema_version: BODY_PHOTO_FLOW_SCHEMA_VERSION,
    session_id: "session-1",
    side_profile: "left",
    stage: "capture",
    updated_at: 100,
  };

  expect(reconcileBodyPhotoFlowDraft(draft, session([
    { view: "front" },
    { view: "side" },
  ] as BodyPhotoSession["photos"]))).toMatchObject({
    capture_mode: "library",
    current_view: "back",
    ghost_scale: 0.9,
    side_profile: "left",
    stage: "capture",
  });
});

it("rejects malformed or cross-session drafts at the storage boundary", () => {
  const draft = createBodyPhotoFlowDraft("initial_plan", "session-1");
  const encoded = serializeBodyPhotoFlowDraft(draft);

  expect(parseBodyPhotoFlowDraft(encoded)).toEqual(draft);
  expect(parseBodyPhotoFlowDraft(JSON.stringify({ ...draft, session_id: "session-2" }), "session-1")).toBeNull();
  expect(parseBodyPhotoFlowDraft(JSON.stringify({ ...draft, ghost_scale: 3 }))).toBeNull();
  expect(parseBodyPhotoFlowDraft("not-json")).toBeNull();
});
