import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";

const api = vi.hoisted(() => ({
  deleteBodyPhotoSession: vi.fn(),
  getBodyPhotoSessions: vi.fn(),
}));
vi.mock("./api", () => api);

import { BodyProgressPage } from "./BodyProgressPage";

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("links each photo session to its result and keeps the workflow optional", async () => {
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [{
      id: "session-1",
      purpose: "initial_plan",
      state: "review_pending",
      photos: [{
        id: "photo-1",
        view: "front",
        content_url: "/api/v1/body-photos/photos/photo-1/content",
        created_at: "2026-08-03T10:00:00Z",
      }],
      operational_processing_consent: null,
      model_training_consent: null,
      submitted_at: "2026-08-03T10:00:00Z",
      created_at: "2026-08-03T10:00:00Z",
      updated_at: "2026-08-03T10:00:00Z",
    }],
  });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  expect(await screen.findByRole("link", { name: /view analysis/i })).toHaveAttribute(
    "href",
    "/body-progress/session-1",
  );
  expect(screen.getByRole("heading", { name: "Body Analysis" })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Body Analysis" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Latest progress photo" })).toHaveAttribute("src", "/api/v1/body-photos/photos/photo-1/content");
  expect(screen.getByText(/Optional — add standardized/i)).toBeInTheDocument();
});

it("uses the Bod scanner visual and shows an actionable empty state", async () => {
  api.getBodyPhotoSessions.mockResolvedValue({ items: [] });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "No photo registered" })).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Body analysis scanner preview" })).toHaveAttribute(
    "src",
    "/body-analysis/Bod.png",
  );
  expect(screen.getByRole("link", { name: "Register new photos" })).toHaveAttribute(
    "href",
    "/body-progress/new",
  );
  expect(screen.queryByText("پیشرفت بدنی")).not.toBeInTheDocument();
});

it("separates incomplete uploads from submitted analyses and marks the latest analysis", async () => {
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [
      {
        id: "incomplete-1",
        purpose: "progress_check",
        state: "uploading",
        photos: [{ id: "front", view: "front", content_url: "/front" }],
        submitted_at: null,
        created_at: "2026-08-04T10:00:00Z",
        updated_at: "2026-08-04T10:00:00Z",
      },
      {
        id: "analysis-1",
        purpose: "initial_plan",
        state: "completed",
        photos: [{ id: "analysis-front", view: "front", content_url: "/analysis-front" }],
        submitted_at: "2026-08-03T10:00:00Z",
        created_at: "2026-08-03T10:00:00Z",
        updated_at: "2026-08-03T10:00:00Z",
      },
    ],
  });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "Incomplete uploads" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Saved analyses" })).toBeVisible();
  expect(screen.getByRole("link", { name: "Continue upload" })).toHaveAttribute(
    "href",
    "/body-progress/new?sessionId=incomplete-1",
  );
  expect(screen.getByRole("link", { name: "View analysis" })).toHaveAttribute(
    "href",
    "/body-progress/analysis-1",
  );
  expect(screen.getByText("Latest analysis")).toBeVisible();
  expect(screen.getAllByText(/1\/3/)).toHaveLength(2);
});

it("deletes an incomplete session after confirmation", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("confirm", vi.fn(() => true));
  api.deleteBodyPhotoSession.mockResolvedValue(undefined);
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [{
      id: "incomplete-1",
      purpose: "progress_check",
      state: "uploading",
      photos: [{ id: "front", view: "front", content_url: "/front" }],
      submitted_at: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    }],
  });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "Delete upload" }));

  await waitFor(() => expect(api.deleteBodyPhotoSession).toHaveBeenCalledWith("incomplete-1"));
  expect(screen.queryByRole("link", { name: "Continue upload" })).not.toBeInTheDocument();
});

it("keeps an incomplete session and shows an inline error when deletion fails", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("confirm", vi.fn(() => true));
  api.deleteBodyPhotoSession.mockRejectedValue(new Error("storage unavailable"));
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [{
      id: "incomplete-1",
      purpose: "progress_check",
      state: "uploading",
      photos: [],
      submitted_at: null,
      created_at: "2026-08-04T10:00:00Z",
      updated_at: "2026-08-04T10:00:00Z",
    }],
  });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  await user.click(await screen.findByRole("button", { name: "Delete upload" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Upload could not be deleted");
  expect(screen.getByRole("link", { name: "Continue upload" })).toBeVisible();
});
