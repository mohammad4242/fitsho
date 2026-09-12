import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  deleteProfilePhoto: vi.fn(),
  uploadProfilePhoto: vi.fn(),
}));

vi.mock("./api", () => api);

import { ProfilePhotoAvatar, ProfilePhotoControl } from "./ProfilePhoto";

beforeEach(() => {
  vi.clearAllMocks();
});

it("renders the private image when a URL is available and keeps a useful fallback", () => {
  const { rerender } = render(<ProfilePhotoAvatar url="/private/photo" label="محمد رضایی" />);

  expect(screen.getByRole("img", { name: "محمد رضایی" })).toHaveAttribute("src", "/private/photo");

  rerender(<ProfilePhotoAvatar label="محمد رضایی" />);
  expect(screen.queryByRole("img", { name: "محمد رضایی" })).toBeInTheDocument();
  expect(screen.getByText("م")).toBeInTheDocument();
});

it("rejects unsupported files before making an upload request", async () => {
  render(<ProfilePhotoControl initialUrl={null} label="محمد رضایی" />);

  const input = screen.getByLabelText("انتخاب عکس پروفایل");
  fireEvent.change(input, { target: { files: [new File(["gif"], "avatar.gif", { type: "image/gif" })] } });

  expect(await screen.findByRole("alert")).toHaveTextContent("فرمت عکس پشتیبانی نمی‌شود");
  expect(api.uploadProfilePhoto).not.toHaveBeenCalled();
});

it("offers HEIC and HEIF files from iPhone photo libraries", () => {
  render(<ProfilePhotoControl initialUrl={null} label="محمد رضایی" />);

  expect(screen.getByLabelText("انتخاب عکس پروفایل")).toHaveAttribute(
    "accept",
    "image/jpeg,image/png,image/webp,image/heic,image/heif",
  );
});

it("opens a square crop preview before uploading a supported file", async () => {
  render(<ProfilePhotoControl initialUrl={null} label="محمد رضایی" />);
  fireEvent.change(screen.getByLabelText("انتخاب عکس پروفایل"), {
    target: { files: [new File(["png"], "avatar.png", { type: "image/png" })] },
  });

  expect(await screen.findByRole("dialog", { name: "قاب مربعی عکس" })).toBeInTheDocument();
  expect(screen.getByText("از مرکز تصویر به‌صورت مربعی برش می‌خورد.")).toBeInTheDocument();
});

it("deletes an existing photo after explicit confirmation", async () => {
  const user = userEvent.setup();
  api.deleteProfilePhoto.mockResolvedValue(undefined);
  const onChanged = vi.fn();
  render(<ProfilePhotoControl initialUrl="/private/photo?v=1" label="محمد رضایی" onChanged={onChanged} />);

  vi.spyOn(window, "confirm").mockReturnValue(true);
  await user.click(screen.getByRole("button", { name: "حذف عکس" }));

  expect(api.deleteProfilePhoto).toHaveBeenCalledOnce();
  expect(onChanged).toHaveBeenCalledWith(null);
});
