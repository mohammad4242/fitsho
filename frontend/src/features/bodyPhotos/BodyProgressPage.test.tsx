import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";

const api = vi.hoisted(() => ({ getBodyPhotoSessions: vi.fn() }));
vi.mock("./api", () => api);

import { BodyProgressPage } from "./BodyProgressPage";

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
});

it("links each photo session to its result and keeps the workflow optional", async () => {
  api.getBodyPhotoSessions.mockResolvedValue({
    items: [{
      id: "session-1",
      purpose: "initial_plan",
      state: "review_pending",
      photos: [],
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
  expect(screen.getByRole("list", { name: "Body progress" })).toBeInTheDocument();
  expect(screen.getByText(/Optional — add standardized/i)).toBeInTheDocument();
});
