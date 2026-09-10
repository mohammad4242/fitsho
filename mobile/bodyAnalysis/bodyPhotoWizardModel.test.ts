import { expect, it } from "vitest";

import type { BodyPhotoSession } from "@fitician/core/body-photos";

import { createBodyPhotoFlowDraft } from "./bodyPhotoFlow";
import {
  bodyPhotoPurposeFromParam,
  draftForCapturedBodyPhoto,
  isResumableBodyPhotoSession,
  nextLocalBodyPhotoView,
  pendingLocalBodyPhotoViews,
} from "./bodyPhotoWizardModel";

function session(state: BodyPhotoSession["state"]): BodyPhotoSession {
  return {
    created_at: "2026-09-08T10:00:00Z",
    id: "session-1",
    model_training_consent: null,
    operational_processing_consent: null,
    photos: [],
    purpose: "initial_plan",
    state,
    submitted_at: null,
    updated_at: "2026-09-08T10:00:00Z",
  };
}

it("accepts only the supported session purposes from a route parameter", () => {
  expect(bodyPhotoPurposeFromParam("cycle_completion")).toBe("cycle_completion");
  expect(bodyPhotoPurposeFromParam("progress_check")).toBe("progress_check");
  expect(bodyPhotoPurposeFromParam("admin")).toBe("initial_plan");
  expect(bodyPhotoPurposeFromParam(undefined)).toBe("initial_plan");
});

it("resumes only editable body-photo sessions", () => {
  expect(isResumableBodyPhotoSession(session("draft"))).toBe(true);
  expect(isResumableBodyPhotoSession(session("failed"))).toBe(true);
  expect(isResumableBodyPhotoSession(session("completed"))).toBe(false);
  expect(isResumableBodyPhotoSession(session("deleted"))).toBe(false);
});

it("advances local captures while honoring views already on the server", () => {
  const existing = session("draft");
  existing.photos.push({ view: "front" } as BodyPhotoSession["photos"][number]);

  expect(nextLocalBodyPhotoView(existing, [], "side")).toBe("back");
  expect(nextLocalBodyPhotoView(existing, ["back"], "side")).toBeNull();
});

it("keeps an uncaptured current view in the persisted draft for safe resume", () => {
  const draft = createBodyPhotoFlowDraft("initial_plan", "session-1");
  const next = draftForCapturedBodyPhoto(draft, "front", "side");

  expect(next.current_view).toBe("side");
  expect(next.capture_mode).toBe("library");
  expect(JSON.stringify(next)).not.toMatch(/uri|bytes|base64|pixels/i);
});

it("returns to the web upload mode after a camera capture", () => {
  const draft = createBodyPhotoFlowDraft("initial_plan", "session-1");
  const next = draftForCapturedBodyPhoto(draft, "front", "side");

  expect(next.capture_mode).toBe("library");
});

it("orders any legacy local uploads as front, side, then back", () => {
  const existing = session("draft");
  existing.photos.push({ view: "side" } as BodyPhotoSession["photos"][number]);

  expect(pendingLocalBodyPhotoViews(existing, ["back", "front"])).toEqual(["front", "back"]);
});
