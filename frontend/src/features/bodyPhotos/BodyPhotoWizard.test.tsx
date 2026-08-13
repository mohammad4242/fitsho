import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
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

const file = new File(["user-cropped-headless-bytes"], "front.jpg", { type: "image/jpeg" });

function processed(view: "front" | "side" | "back"): ProcessedBodyPhoto {
  return {
    file: new File([`standardized-${view}`], `${view}.jpg`, { type: "image/jpeg" }),
    previewUrl: `blob:preview-${view}`,
    validation: {
      isValid: true,
      expectedView: view,
      viewAssessment: view === "side" ? "matched" : "ambiguous",
      quality: {
        brightnessScore: 0.9,
        sharpnessScore: 0.9,
        minimumLandmarkVisibility: 0.9,
      },
      visibleLandmarks: ["shoulders", "arms", "hips", "knees", "ankles", "feet"],
    },
  };
}

function renderWizard(processor?: BodyPhotoProcessor, entry = "/body-progress/new") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <BodyPhotoWizard processor={processor} />
      <LocationDisplay />
    </MemoryRouter>,
  );
}

function LocationDisplay() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
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
  expect(await screen.findByAltText(/standardized front preview/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeDisabled();
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.uploadBodyPhoto).not.toHaveBeenCalled();

  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeEnabled();
});

it("explains how to recover when the phone origin is not trusted", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("front")) };
  api.createBodyPhotoSession.mockRejectedValueOnce(
    new ApiError(403, "Untrusted request origin"),
  );
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /current phone address is not trusted by fitsho/i,
  );
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

it("returns to the result after a successful replacement cannot start analysis", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("side")) };
  api.startBodyPhotoAnalysis.mockRejectedValueOnce(new Error("retry limit"));
  renderWizard(processor, "/body-progress/new?sessionId=session-2&view=side");

  await screen.findByRole("heading", { name: /side photo/i });
  await user.upload(screen.getByLabelText(/side photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));

  await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/body-progress/session-2"));
  expect(screen.queryByText(/standardized photo could not be uploaded/i)).not.toBeInTheDocument();
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

it("requires a phone-cropped headless photo and lists every retained body region", async () => {
  await i18n.changeLanguage("fa");
  renderWizard();

  expect(screen.getByText("لطفاً حتماً قبل از ارسال عکس، عکس را کراپ کرده و چهره را حذف کنید")).toBeVisible();
  expect(screen.getByLabelText(/راهنمای کادر عکس بدون چهره/)).toHaveTextContent(
    /شانه‌ها.*بازوها.*کمر و باسن.*زانوها.*مچ پا و کف پا/,
  );
  expect(screen.queryByRole("button", { name: /گرفتن عکس/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText(/بارگذاری عکس روبه‌رو/)).toBeInTheDocument();
});

it("processes three views, allows retake, and uploads only standardized files", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  await user.click(screen.getByRole("button", { name: /retake front/i }));
  expect(screen.queryByAltText(/standardized front preview/i)).not.toBeInTheDocument();
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

it("revokes standardized preview URLs when a photo is replaced and on unmount", async () => {
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

it("shows only measured quality feedback for a standardized preview", async () => {
  const user = userEvent.setup();
  renderWizard({ process: vi.fn().mockResolvedValue(processed("front")) });

  await user.upload(screen.getByLabelText(/front photo upload/i), file);

  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/lighting/i);
  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/landmark visibility/i);
  expect(screen.getByLabelText(/photo check/i)).not.toHaveTextContent(/overall quality/i);
});

it.each([
  ["shoulders_not_visible", /shoulders are not fully visible/i],
  ["legs_or_feet_not_visible", /legs, ankles, and feet must remain fully inside/i],
  ["body_out_of_frame", /part of the body is outside the frame/i],
  ["image_too_blurry", /image is too blurry/i],
  ["insufficient_lighting", /lighting is not sufficient/i],
  ["unexpected_body_view", /does not match the required view/i],
  ["multiple_people_detected", /more than one person was detected/i],
] as const)("shows the actionable %s error", async (code, message) => {
  const user = userEvent.setup();
  renderWizard({ process: vi.fn().mockRejectedValue(new BodyPhotoProcessingError(code)) });
  await user.upload(screen.getByLabelText(/front photo upload/i), file);
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
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
