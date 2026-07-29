import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import type { AdminExercise } from "./types";

const adminApi = vi.hoisted(() => ({ getAdminExercises: vi.fn() }));
vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminExercisesPage } from "./AdminExercisesPage";

const exercise: AdminExercise = {
  id: "1",
  slug: "incline-push-up",
  name_en: "Incline Push Up",
  name_fa: "شنا سوئدی شیب‌دار",
  body_region: "upper_body",
  primary_muscle: "chest",
  secondary_muscles: ["triceps"],
  equipment: ["bodyweight"],
  difficulty: "beginner",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: [],
  labels: [],
  needs_review: false,
  is_programmable: true,
  instructions_en: ["One", "Two", "Three"],
  instructions_fa: ["یک", "دو", "سه"],
  safety_notes_en: ["Safe"],
  safety_notes_fa: ["ایمن"],
  media_path: "/exercises/exercise-placeholder.svg",
  media_type: "placeholder",
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  is_active: false,
  created_at: "2026-07-27T00:00:00Z",
  updated_at: "2026-07-27T00:00:00Z",
};

beforeEach(() => adminApi.getAdminExercises.mockReset());

it("renders inactive exercises and a clear add action", async () => {
  adminApi.getAdminExercises.mockResolvedValue({
    items: [exercise], page: 1, page_size: 20, total: 1, total_pages: 1,
  });
  renderPage();

  expect(await screen.findByText("شنا سوئدی شیب‌دار")).toBeInTheDocument();
  expect(screen.getByText("غیرفعال")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "افزودن حرکت" })).toHaveAttribute(
    "href", "/admin/exercises/new",
  );
  expect(screen.getByRole("link", { name: "ویرایش" })).toHaveAttribute(
    "href", "/admin/exercises/1/edit",
  );
});

it("announces creation and focuses the created exercise", async () => {
  adminApi.getAdminExercises.mockResolvedValue({
    items: [exercise], page: 1, page_size: 20, total: 1, total_pages: 1,
  });
  render(
    <MemoryRouter initialEntries={[{
      pathname: "/admin/exercises",
      state: { createdId: exercise.id },
    }]}>
      <AdminExercisesPage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("حرکت با موفقیت ساخته شد.")).toBeInTheDocument();
  const createdExercise = screen.getByRole("article");
  expect(createdExercise).toHaveFocus();
  expect(screen.getByRole("link", { name: "رفتن به حرکت ساخته‌شده" })).toHaveAttribute(
    "href", `#exercise-${exercise.id}`,
  );
});

it("shows loading and retries a failed list request", async () => {
  adminApi.getAdminExercises
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 });
  const user = userEvent.setup();
  renderPage();

  expect(screen.getByRole("status")).toHaveTextContent("در حال دریافت حرکات");
  expect(await screen.findByRole("alert")).toHaveTextContent("دریافت نشد");
  await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));
  expect(await screen.findByText(/هنوز حرکتی ثبت نشده است/)).toBeInTheDocument();
  expect(adminApi.getAdminExercises).toHaveBeenCalledTimes(2);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminExercisesPage />
    </MemoryRouter>,
  );
}
