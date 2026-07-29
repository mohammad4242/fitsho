import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ApiError } from "../../shared/apiClient";

const adminApi = vi.hoisted(() => ({ createAdminExercise: vi.fn() }));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminExerciseNewPage } from "./AdminExerciseNewPage";

beforeEach(() => {
  adminApi.createAdminExercise.mockReset();
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:preview"),
    revokeObjectURL: vi.fn(),
  });
});

afterEach(() => vi.unstubAllGlobals());

it("renders bilingual fields, placeholder, and RTL/LTR directions", () => {
  renderPage();

  expect(screen.getByLabelText("نام انگلیسی")).toHaveAttribute("dir", "ltr");
  expect(screen.getByLabelText("نام فارسی")).toHaveAttribute("dir", "rtl");
  expect(screen.getByRole("img", { name: /نمایش حرکت/ })).toHaveAttribute(
    "src", "/exercises/exercise-placeholder.svg",
  );
});

it("suggests an editable slug and filters muscles by region", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.type(screen.getByLabelText("نام انگلیسی"), "Incline Push Up");
  expect(screen.getByLabelText("شناسه پایدار")).toHaveValue("incline-push-up");
  await user.selectOptions(screen.getByLabelText("ناحیه بدن"), "upper_body");
  expect(screen.getByLabelText("عضله اصلی")).toContainHTML("chest");
  expect(screen.getByLabelText("عضله اصلی")).not.toContainHTML("quadriceps");
});

it("supports repeatable instructions and safety notes plus multi-select choices", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "افزودن مرحله انگلیسی" }));
  await user.click(screen.getByRole("button", { name: "افزودن نکته فارسی" }));
  await user.click(screen.getByLabelText("وزن بدن"));
  await user.selectOptions(screen.getByLabelText("ناحیه بدن"), "upper_body");
  await user.click(screen.getByLabelText("عضله فرعی: پشت بازو"));

  expect(screen.getByLabelText("مرحله انگلیسی ۴")).toBeInTheDocument();
  expect(screen.getByLabelText("نکته فارسی ۲")).toBeInTheDocument();
  expect(screen.getByLabelText("وزن بدن")).toBeChecked();
  expect(screen.getByLabelText("عضله فرعی: پشت بازو")).toBeChecked();
});

it("previews GIF and video selections without autoplay", () => {
  renderPage();
  const input = screen.getByLabelText("فایل GIF یا ویدئو");
  fireEvent.change(input, {
    target: { files: [new File(["GIF89a"], "demo.gif", { type: "image/gif" })] },
  });
  expect(screen.getByRole("img", { name: /نمایش حرکت/ })).toHaveAttribute("src", "blob:preview");

  fireEvent.change(input, {
    target: { files: [new File(["video"], "demo.mp4", { type: "video/mp4" })] },
  });
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview");
  const video = screen.getByLabelText(/نمایش حرکت/);
  expect(video.tagName).toBe("VIDEO");
  expect(video).not.toHaveAttribute("autoplay");
});

it("submits separate male and female media assets", async () => {
  adminApi.createAdminExercise.mockResolvedValue({ id: "created-id" });
  const user = userEvent.setup();
  renderPage();
  await fillMinimumForm(user);
  const maleVideo = new File(["video"], "male.mp4", { type: "video/mp4" });
  const femaleThumbnail = new File(["image"], "female.jpg", { type: "image/jpeg" });

  await user.upload(screen.getByLabelText("ویدئوی مرد"), maleVideo);
  await user.upload(screen.getByLabelText("تصویر بندانگشتی زن"), femaleThumbnail);
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));

  expect(adminApi.createAdminExercise).toHaveBeenCalledWith(
    expect.objectContaining({
      media_assets: [
        expect.objectContaining({ presentation: "male", role: "video" }),
        expect.objectContaining({ presentation: "female", role: "thumbnail" }),
      ],
    }),
    null,
    expect.objectContaining({
      male_video: maleVideo,
      female_thumbnail: femaleThumbnail,
    }),
  );
});

it("announces validation errors and does not submit an empty form", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));

  expect(screen.getByRole("alert")).toHaveTextContent("فیلدهای مشخص‌شده");
  expect(screen.getByText(/حداقل یک وسیله را انتخاب کنید/)).toBeInTheDocument();
  expect(adminApi.createAdminExercise).not.toHaveBeenCalled();
});

it("shows loading then navigates after successful submission", async () => {
  let resolveRequest: (value: object) => void = () => undefined;
  adminApi.createAdminExercise.mockImplementation(
    () => new Promise((resolve) => { resolveRequest = resolve; }),
  );
  const user = userEvent.setup();
  renderPage();
  await fillMinimumForm(user);
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));
  expect(screen.getByRole("button", { name: "در حال ذخیره…" })).toBeDisabled();
  resolveRequest({ id: "created-id" });
  expect(await screen.findByText("LIST PAGE")).toBeInTheDocument();
});

it("shows duplicate slug and retryable API failures", async () => {
  adminApi.createAdminExercise
    .mockRejectedValueOnce(new ApiError(409, "Exercise slug already exists"))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ id: "created-id" });
  const user = userEvent.setup();
  renderPage();
  await fillMinimumForm(user);

  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "این شناسه قبلاً استفاده شده است",
  );
  await user.clear(screen.getByLabelText("شناسه پایدار"));
  await user.type(screen.getByLabelText("شناسه پایدار"), "incline-push-up-2");
  await user.click(screen.getByRole("button", { name: "ذخیره حرکت" }));
  expect(await screen.findByRole("button", { name: "تلاش دوباره" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));
  expect(await screen.findByText("LIST PAGE")).toBeInTheDocument();
});

async function fillMinimumForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("نام انگلیسی"), "Incline Push Up");
  await user.type(screen.getByLabelText("نام فارسی"), "شنا شیب‌دار");
  await user.selectOptions(screen.getByLabelText("ناحیه بدن"), "upper_body");
  await user.selectOptions(screen.getByLabelText("عضله اصلی"), "chest");
  await user.click(screen.getByLabelText("وزن بدن"));
  const digits = ["۱", "۲", "۳"];
  for (const [index, value] of ["Brace", "Lower", "Press"].entries()) {
    await user.type(screen.getByLabelText(`مرحله انگلیسی ${digits[index]}`), value);
    await user.type(screen.getByLabelText(`مرحله فارسی ${digits[index]}`), `مرحله ${index + 1}`);
  }
  await user.type(screen.getByLabelText("نکته انگلیسی ۱"), "Keep aligned");
  await user.type(screen.getByLabelText("نکته فارسی ۱"), "بدن هم‌راستا باشد");
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/admin/exercises/new"]}>
      <Routes>
        <Route path="/admin/exercises/new" element={<AdminExerciseNewPage />} />
        <Route path="/admin/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );
}
