import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { BodyAnalysis, BodyPhotoSession } from "./types";

const api = vi.hoisted(() => ({
  getBodyPhotoSession: vi.fn(),
  getBodyPhotoSessions: vi.fn(),
  getBodyPhotoAnalysis: vi.fn(),
  startBodyPhotoAnalysis: vi.fn(),
  retryBodyPhotoAnalysis: vi.fn(),
}));

vi.mock("./api", () => api);

import { BodyAnalysisResultPage } from "./BodyAnalysisResultPage";

const session: BodyPhotoSession = {
  id: "session-2",
  purpose: "progress_check",
  state: "review_pending",
  photos: (["front", "side", "back"] as const).map((view) => ({
    id: `photo-${view}`,
    view,
    mime_type: "image/jpeg",
    byte_size: 120_000,
    width: 1200,
    height: 1800,
    client_crop_confidence: 0.95,
    client_crop_confirmed: true,
    server_geometry_checked: true,
    content_url: `/api/v1/body-photo-sessions/session-2/photos/${view}/content`,
    created_at: "2026-08-03T10:00:00Z",
    updated_at: "2026-08-03T10:00:00Z",
  })),
  operational_processing_consent: {
    granted: true,
    version: "body-photo-processing-v1",
    recorded_at: "2026-08-03T10:00:00Z",
  },
  model_training_consent: null,
  submitted_at: "2026-08-03T10:00:00Z",
  created_at: "2026-08-03T10:00:00Z",
  updated_at: "2026-08-03T10:00:00Z",
};

const analysis: BodyAnalysis = {
  id: "analysis-2",
  session_id: session.id,
  revision: 1,
  status: "review_pending",
  provider: "openrouter",
  model_id: "vision-model",
  schema_version: "1.0",
  result_version: 1,
  result_source: "ai",
  normalized_result: {
    schema_version: "1.0",
    overall_confidence: 0.81,
    findings: [
      {
        body_area: "arms",
        classification: "strength",
        severity: null,
        confidence: 0.88,
        supporting_views: ["front", "back"],
        explanation: "Arm development appears visually balanced relative to the torso.",
        limitations: [],
        suggested_training_emphasis: [],
        medical_review_recommended: false,
      },
      {
        body_area: "calves",
        classification: "mild_lag",
        severity: 0.52,
        confidence: 0.77,
        supporting_views: ["side", "back"],
        explanation: "Calves appear relatively less developed in the available views.",
        limitations: ["lighting"],
        suggested_training_emphasis: ["calves"],
        medical_review_recommended: false,
      },
      {
        body_area: "shoulders",
        classification: "clear_lag",
        severity: 0.78,
        confidence: 0.86,
        supporting_views: ["front", "back"],
        explanation: "Shoulders appear relatively lagging in visible proportion.",
        limitations: [],
        suggested_training_emphasis: ["lateral_deltoid", "rear_deltoid"],
        medical_review_recommended: false,
      },
      {
        body_area: "hamstrings",
        classification: "uncertain",
        severity: null,
        confidence: 0.39,
        supporting_views: ["side", "back"],
        explanation: "The area is not visible clearly enough.",
        limitations: ["clothing_occlusion"],
        suggested_training_emphasis: [],
        medical_review_recommended: false,
      },
    ],
    summary: {
      visible_strengths: ["arms"],
      priority_areas: ["shoulders"],
      moderate_attention_areas: ["calves"],
      uncertain_areas: ["hamstrings"],
    },
    requires_coach_review: true,
    requires_doctor_review: true,
  },
  overall_confidence: 0.81,
  coach_review: {
    role: "coach",
    decision: "approved",
    reviewed_at: "2026-08-03T12:00:00Z",
    reviewed_result_version: 1,
  },
  doctor_review: {
    role: "doctor",
    decision: null,
    reviewed_at: null,
    reviewed_result_version: null,
  },
  fully_reviewed: false,
  unverified_warning: true,
  safe_error_message: null,
  photo_validation: null,
  created_at: "2026-08-03T10:00:00Z",
  completed_at: "2026-08-03T10:01:00Z",
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/body-progress/session-2"]}>
      <Routes>
        <Route path="/body-progress/:sessionId" element={<BodyAnalysisResultPage />} />
        <Route path="/workout-plan" element={<h1>Workout plan destination</h1>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  api.getBodyPhotoSession.mockResolvedValue(session);
  api.getBodyPhotoSessions.mockResolvedValue({ items: [session] });
  api.getBodyPhotoAnalysis.mockResolvedValue(analysis);
});

it("shows protected thumbnails, confidence, four labeled finding groups, and review states", async () => {
  renderPage();

  expect(await screen.findByRole("heading", { name: /body analysis/i })).toBeInTheDocument();
  expect(screen.getAllByRole("img", { name: /anonymized/i })).toHaveLength(3);
  expect(screen.getByText("81%")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /visible strengths/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /needs attention/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /priority areas/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /not enough information/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/coach review approved/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/doctor review pending/i)).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/not yet been approved by both/i);
  expect(screen.getByRole("link", { name: /view workout plan/i })).toHaveAttribute("href", "/workout-plan");
});

it("shows limitations and never presents a medical diagnosis", async () => {
  renderPage();

  expect(await screen.findByText(/lighting/i)).toBeInTheDocument();
  expect(screen.getByText(/does not diagnose/i)).toBeInTheDocument();
  expect(screen.queryByText(/diagnosed/i)).not.toBeInTheDocument();
});

it("starts a submitted session that has no analysis and shows progress", async () => {
  api.getBodyPhotoSession.mockResolvedValue({ ...session, state: "queued" });
  api.getBodyPhotoAnalysis.mockResolvedValue(null);
  api.startBodyPhotoAnalysis.mockResolvedValue({ ...analysis, status: "queued", normalized_result: null });
  renderPage();

  await waitFor(() => expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-2"));
  expect(await screen.findByRole("status")).toHaveTextContent(/queued/i);
});

it("keeps anonymized photos available when analysis cannot start", async () => {
  api.getBodyPhotoSession.mockResolvedValue({ ...session, state: "queued" });
  api.getBodyPhotoAnalysis.mockResolvedValue(null);
  api.startBodyPhotoAnalysis.mockRejectedValue(new Error("not configured"));
  renderPage();

  expect(await screen.findAllByRole("img", { name: /anonymized/i })).toHaveLength(3);
  expect(screen.getByRole("alert")).toHaveTextContent(/workout plan is still available/i);
  expect(screen.getByRole("button", { name: /retry analysis/i })).toBeInTheDocument();
});

it("compares normalized findings with the most recent prior valid session", async () => {
  const previousSession = {
    ...session,
    id: "session-1",
    created_at: "2026-07-01T10:00:00Z",
  };
  api.getBodyPhotoSessions.mockResolvedValue({ items: [session, previousSession] });
  api.getBodyPhotoAnalysis.mockImplementation(async (sessionId: string) => (
    sessionId === "session-1"
      ? {
          ...analysis,
          id: "analysis-1",
          session_id: "session-1",
          normalized_result: {
            ...analysis.normalized_result,
            findings: [{
              ...analysis.normalized_result?.findings[2],
              body_area: "shoulders",
              classification: "clear_lag",
              severity: 0.88,
              confidence: 0.9,
            }],
            summary: {
              visible_strengths: [],
              priority_areas: ["shoulders"],
              moderate_attention_areas: [],
              uncertain_areas: [],
            },
          },
        }
      : {
          ...analysis,
          normalized_result: {
            ...analysis.normalized_result,
            findings: [{
              ...analysis.normalized_result?.findings[2],
              body_area: "shoulders",
              classification: "mild_lag",
              severity: 0.5,
              confidence: 0.85,
            }],
            summary: {
              visible_strengths: [],
              priority_areas: [],
              moderate_attention_areas: ["shoulders"],
              uncertain_areas: [],
            },
          },
        }
  ));
  renderPage();

  expect(await screen.findByRole("heading", { name: /progress comparison/i })).toBeInTheDocument();
  expect(screen.getByText(/appears improved/i)).toBeInTheDocument();
});

it("offers a retry for failed analysis and preserves a safe error message", async () => {
  const user = userEvent.setup();
  api.getBodyPhotoAnalysis.mockResolvedValue({
    ...analysis,
    status: "failed",
    normalized_result: null,
    overall_confidence: null,
    safe_error_message: "Body analysis could not be completed. Please retry later.",
  });
  api.retryBodyPhotoAnalysis.mockResolvedValue({ ...analysis, status: "queued", normalized_result: null });
  renderPage();

  await user.click(await screen.findByRole("button", { name: /retry analysis/i }));

  expect(api.retryBodyPhotoAnalysis).toHaveBeenCalledWith("session-2");
  expect(await screen.findByRole("status")).toHaveTextContent(/queued/i);
});

it("shows view-specific retake reasons when photo validation rejects an upload", async () => {
  api.getBodyPhotoAnalysis.mockResolvedValue({
    ...analysis,
    status: "failed",
    normalized_result: null,
    overall_confidence: null,
    photo_validation: {
      accepted: false,
      confidence: 0.94,
      issues: [{ view: "front", reasons: ["full_body_not_visible", "low_lighting"] }],
    },
  });
  renderPage();

  const alert = await screen.findByRole("alert");

  expect(alert).toHaveTextContent("Front: Show your full body in the frame");
  expect(alert).toHaveTextContent("Use brighter, even lighting");
});

it("offers editing only for the rejected photo view", async () => {
  api.getBodyPhotoAnalysis.mockResolvedValue({
    ...analysis,
    status: "failed",
    normalized_result: null,
    overall_confidence: null,
    photo_validation: {
      accepted: false,
      confidence: 0.94,
      issues: [{ view: "side", reasons: ["wrong_view"] }],
    },
  });
  renderPage();

  const edit = await screen.findByRole("link", { name: /edit side photo/i });

  expect(edit).toHaveAttribute("href", "/body-progress/new?sessionId=session-2&view=side");
  expect(screen.queryByRole("link", { name: /edit front photo/i })).not.toBeInTheDocument();
});
