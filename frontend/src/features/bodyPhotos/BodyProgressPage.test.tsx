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

  expect(await screen.findByRole("link", { name: "Start photo session" })).toHaveAttribute(
    "href",
    "/body-progress/new",
  );
  await user.click(await screen.findByRole("button", { name: "Delete upload" }));
  expect(screen.getByRole("dialog", { name: "Delete incomplete upload?" })).toBeVisible();
  expect(api.deleteBodyPhotoSession).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Delete permanently" }));

  await waitFor(() => expect(api.deleteBodyPhotoSession).toHaveBeenCalledWith("incomplete-1"));
  expect(screen.queryByRole("link", { name: "Continue upload" })).not.toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("offers deletion for a saved analysis and restores focus after cancel", async () => {
  const user = userEvent.setup();
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [{
      id: "analysis-1",
      purpose: "initial_plan",
      state: "completed",
      photos: [{ id: "front", view: "front", content_url: "/front" }],
      submitted_at: "2026-08-03T10:00:00Z",
      created_at: "2026-08-03T10:00:00Z",
      updated_at: "2026-08-03T10:00:00Z",
    }],
  });
  render(<MemoryRouter><BodyProgressPage /></MemoryRouter>);

  const deleteButton = await screen.findByRole("button", { name: "Delete analysis" });
  await user.click(deleteButton);

  expect(screen.getByRole("dialog", { name: "Delete saved analysis?" })).toHaveTextContent(
    /stored photos and this analysis session will be removed/i,
  );
  await user.click(screen.getByRole("button", { name: "Keep session" }));

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(deleteButton).toHaveFocus();
  expect(api.deleteBodyPhotoSession).not.toHaveBeenCalled();
});

it("closes the delete dialog with Escape", async () => {
  const user = userEvent.setup();
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
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.keyboard("{Escape}");

  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("keeps the dialog open after a deletion failure and allows retry", async () => {
  const user = userEvent.setup();
  api.deleteBodyPhotoSession
    .mockRejectedValueOnce(new Error("storage unavailable"))
    .mockResolvedValueOnce(undefined);
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
  await user.click(screen.getByRole("button", { name: "Delete permanently" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Session could not be deleted");
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Delete permanently" }));

  await waitFor(() => expect(api.deleteBodyPhotoSession).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
