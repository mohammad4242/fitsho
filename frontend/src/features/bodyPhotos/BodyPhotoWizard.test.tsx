import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import {
  BodyPhotoProcessingError,
  type BodyPhotoProcessor,
  type ProcessedBodyPhoto,
} from "./processor";

const api = vi.hoisted(() => ({
  createBodyPhotoSession: vi.fn(),
  getBodyPhotoSession: vi.fn(),
  uploadBodyPhoto: vi.fn(),
  submitBodyPhotoSession: vi.fn(),
  startBodyPhotoAnalysis: vi.fn(),
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

function renderWizard(processor?: BodyPhotoProcessor, entry = "/body-progress/new") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <BodyPhotoWizard processor={processor} />
    </MemoryRouter>,
  );
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  api.createBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "draft", photos: [] });
  api.getBodyPhotoSession.mockResolvedValue({
    id: "session-2",
    state: "failed",
    photos: [],
    operational_processing_consent: { granted: true },
    model_training_consent: { granted: false },
  });
  api.uploadBodyPhoto.mockResolvedValue({ id: "session-1", state: "uploading", photos: [] });
  api.submitBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "queued", photos: [] });
  api.startBodyPhotoAnalysis.mockResolvedValue({ id: "analysis-1", status: "queued" });
});

afterEach(() => {
  vi.unstubAllGlobals();
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
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.uploadBodyPhoto).not.toHaveBeenCalled();

  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeEnabled();
});

it("replaces only the rejected view in an existing photo session", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("side")) };
  renderWizard(processor, "/body-progress/new?sessionId=session-2&view=side");

  expect(await screen.findByRole("heading", { name: /side photo/i })).toBeInTheDocument();
  await user.upload(screen.getByLabelText(/side photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));

  await waitFor(() => expect(api.uploadBodyPhoto).toHaveBeenCalledWith(
    "session-2",
    "side",
    expect.objectContaining({ file: expect.any(File) }),
  ));
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.submitBodyPhotoSession).toHaveBeenCalledWith("session-2", true, false);
  expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-2");
});

it("does not report a successful replacement as an upload failure", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("side")) };
  api.startBodyPhotoAnalysis.mockRejectedValueOnce(new Error("retry limit"));
  renderWizard(processor, "/body-progress/new?sessionId=session-2&view=side");

  await screen.findByRole("heading", { name: /side photo/i });
  await user.upload(screen.getByLabelText(/side photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /photos were submitted successfully, but body analysis has not started/i,
  );
});

it("shows the selected photo immediately while anonymization is processing", async () => {
  const user = userEvent.setup();
  let resolveProcessing: ((value: ProcessedBodyPhoto) => void) | undefined;
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:selected-front"),
    revokeObjectURL: vi.fn(),
  });
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation(() => new Promise<ProcessedBodyPhoto>((resolve) => {
      resolveProcessing = resolve;
    })),
  };
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);

  expect(await screen.findByAltText(/selected front preview/i)).toHaveAttribute(
    "src",
    "blob:selected-front",
  );

  resolveProcessing?.(processed("front"));
});

it("shows fitted-clothing guidance on every capture step", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  expect(screen.getAllByText(/athletic shorts and fitted, minimal athletic clothing/i)).not.toHaveLength(0);
  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));
  await waitFor(() => expect(screen.getByLabelText(/side photo upload/i)).toBeInTheDocument());
  expect(screen.getByText(/athletic shorts and fitted, minimal athletic clothing/i)).toBeInTheDocument();
});

it("offers separate actions for taking a photo and uploading an existing photo", () => {
  renderWizard();

  expect(screen.getByRole("button", { name: /take front photo/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/upload an existing front photo/i)).toBeInTheDocument();
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

it("starts analysis immediately after a successful submission", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  for (const view of ["front", "side", "back"] as const) {
    await user.upload(await screen.findByLabelText(new RegExp(`${view} photo upload`, "i")), file);
    if (view === "front") {
      await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
    }
    await user.click(screen.getByRole("button", { name: new RegExp(`confirm and upload ${view}`, "i") }));
  }

  await user.click(await screen.findByRole("button", { name: /submit photos/i }));
  await waitFor(() => expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-1"));
});

it("explains that photos were submitted when body analysis cannot start", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  api.startBodyPhotoAnalysis.mockRejectedValue(new ApiError(503, "Body photo analysis is temporarily unavailable"));
  renderWizard(processor);

  for (const view of ["front", "side", "back"] as const) {
    await user.upload(await screen.findByLabelText(new RegExp(`${view} photo upload`, "i")), file);
    if (view === "front") {
      await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
    }
    await user.click(screen.getByRole("button", { name: new RegExp(`confirm and upload ${view}`, "i") }));
  }

  await user.click(await screen.findByRole("button", { name: /submit photos/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /photos were submitted successfully, but body analysis has not started/i,
  );
  expect(api.submitBodyPhotoSession).toHaveBeenCalledWith("session-1", true, false);
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

it("shows structured quality feedback for an anonymized preview", async () => {
  const user = userEvent.setup();
  renderWizard({ process: vi.fn().mockResolvedValue(processed("front")) });

  await user.upload(screen.getByLabelText(/front photo upload/i), file);

  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/overall quality/i);
  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/pose and framing/i);
});

it("shows a distinct clothing rejection and keeps the repeated clothing guidance visible", async () => {
  const user = userEvent.setup();
  renderWizard({
    process: vi.fn().mockRejectedValue(new BodyPhotoProcessingError("clothing_hides_body_contours")),
  });

  await user.upload(screen.getByLabelText(/front photo upload/i), file);

  expect(await screen.findByRole("alert")).toHaveTextContent(/clothing hides body contours/i);
  expect(screen.getByLabelText(/clothing and coverage/i)).toBeInTheDocument();
});

it("releases a late preview when processing resolves after the wizard unmounts", async () => {
  const user = userEvent.setup();
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  let resolveProcessing: ((value: ProcessedBodyPhoto) => void) | undefined;
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation(() => new Promise<ProcessedBodyPhoto>((resolve) => {
      resolveProcessing = resolve;
    })),
  };
  const rendered = renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  rendered.unmount();
  resolveProcessing?.({ ...processed("front"), previewUrl: "blob:late-preview" });

  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:late-preview"));
});
