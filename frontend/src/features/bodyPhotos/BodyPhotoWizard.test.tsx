import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { BodyPhotoProcessor, ProcessedBodyPhoto } from "./processor";

const api = vi.hoisted(() => ({
  createBodyPhotoSession: vi.fn(),
  uploadBodyPhoto: vi.fn(),
  submitBodyPhotoSession: vi.fn(),
}));

vi.mock("./api", () => api);

import { BodyPhotoWizard } from "./BodyPhotoWizard";

const file = new File(["original-face-containing-bytes"], "front.jpg", { type: "image/jpeg" });

function processed(view: "front" | "side" | "back"): ProcessedBodyPhoto {
  return {
    file: new File([`cropped-${view}`], `${view}.jpg`, { type: "image/jpeg" }),
    previewUrl: `blob:preview-${view}`,
    originalHeight: 1200,
    cropTop: 240,
    cropBottom: 1080,
    cropConfidence: 0.95,
    processedSha256: "a".repeat(64),
    cropEvidenceSha256: "b".repeat(64),
    validation: {
      isValid: true,
      expectedView: view,
      detectedView: view,
      quality: {
        overallScore: 0.9,
        brightnessScore: 0.9,
        sharpnessScore: 0.9,
        poseScore: 0.9,
        bodyCompletenessScore: 0.9,
        clothingVisibilityScore: 0.9,
        backgroundReliabilityScore: 0.9,
      },
      warnings: [],
      crop: { headRemoved: true, confidence: 0.95 },
    },
  };
}

function renderWizard(processor?: BodyPhotoProcessor) {
  return render(
    <MemoryRouter>
      <BodyPhotoWizard processor={processor} />
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  api.createBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "draft", photos: [] });
  api.uploadBodyPhoto.mockResolvedValue({ id: "session-1", state: "uploading", photos: [] });
  api.submitBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "queued", photos: [] });
});

it("keeps the photo workflow optional and offers a skip path", async () => {
  const user = userEvent.setup();
  renderWizard();

  await user.click(screen.getByRole("link", { name: /skip photos/i }));

  expect(screen.getByText(/you can still receive a complete workout plan/i)).toBeInTheDocument();
});

it("requires operational consent before the confirm upload action is enabled", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("front")) };
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  expect(await screen.findByAltText(/anonymized front preview/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeDisabled();

  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeEnabled();
});

it("shows fitted-clothing guidance on every capture step", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  expect(screen.getByText(/athletic shorts and fitted, minimal athletic clothing/i)).toBeInTheDocument();
  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));
  await waitFor(() => expect(screen.getByLabelText(/side photo upload/i)).toBeInTheDocument());
  expect(screen.getByText(/athletic shorts and fitted, minimal athletic clothing/i)).toBeInTheDocument();
});

it("processes three views, allows retake, and never passes the original file to upload", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /retake front/i }));
  expect(screen.queryByAltText(/anonymized front preview/i)).not.toBeInTheDocument();
  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));
  await user.upload(await screen.findByLabelText(/side photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));
  await user.upload(await screen.findByLabelText(/back photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /confirm and upload back/i }));

  await waitFor(() => expect(api.uploadBodyPhoto).toHaveBeenCalledTimes(3));
  const sentFiles = api.uploadBodyPhoto.mock.calls.map((call) => call[2].file as File);
  expect(sentFiles).not.toContain(file);
  expect(sentFiles.map((item) => item.name)).toEqual(["front.jpg", "side.jpg", "back.jpg"]);
  expect(screen.getByRole("checkbox", { name: /future model-training/i })).not.toBeChecked();
});

it("revokes anonymized preview URLs when a photo is replaced and on unmount", async () => {
  const user = userEvent.setup();
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const processor: BodyPhotoProcessor = {
    process: vi.fn()
      .mockResolvedValueOnce(processed("front"))
      .mockResolvedValueOnce({ ...processed("front"), previewUrl: "blob:replacement" }),
  };
  const rendered = renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  expect(revoke).toHaveBeenCalledWith("blob:preview-front");

  rendered.unmount();
  expect(revoke).toHaveBeenCalledWith("blob:replacement");
});
