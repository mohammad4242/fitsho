import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const adminApi = vi.hoisted(() => ({
  getAdminExercise: vi.fn(),
  updateAdminExercise: vi.fn(),
}));

vi.mock("./api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "1", email: "admin@example.com", created_at: "2026-07-27", is_admin: true },
    logout: vi.fn(),
  }),
}));

import { AdminExerciseEditPage } from "./AdminExerciseEditPage";

const exercise = {
  id: "exercise-id",
  slug: "incline-push-up",
  name_en: "Incline Push Up",
  name_fa: "شنا سوئدی شیب‌دار",
  body_region: "upper_body",
  primary_muscle: "chest",
  secondary_muscles: ["triceps"],
  equipment: ["bodyweight", "bench"],
  difficulty: "beginner",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: ["shoulder_internal_rotation"],
  labels: [],
  needs_review: false,
  is_programmable: true,
  instructions_en: ["Brace", "Lower", "Press"],
  instructions_fa: ["محکم", "پایین", "فشار"],
  safety_notes_en: ["Keep aligned"],
  safety_notes_fa: ["هم‌راستا بمانید"],
  media_path: "/exercises/exercise-placeholder.svg",
  media_type: "placeholder",
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  is_active: true,
  created_at: "2026-07-27T12:00:00Z",
  updated_at: "2026-07-27T12:00:00Z",
};

beforeEach(() => {
  adminApi.getAdminExercise.mockReset();
  adminApi.updateAdminExercise.mockReset();
  adminApi.getAdminExercise.mockResolvedValue(exercise);
  adminApi.updateAdminExercise.mockResolvedValue(exercise);
});

it("loads structured programming metadata and saves an edited exercise", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={["/admin/exercises/exercise-id/edit"]}>
      <Routes>
        <Route path="/admin/exercises/:exerciseId/edit" element={<AdminExerciseEditPage />} />
        <Route path="/exercises" element={<p>LIST PAGE</p>} />
      </Routes>
    </MemoryRouter>,
  );

  expect(await screen.findByLabelText("الگوی حرکت")).toHaveValue("horizontal_push");
  expect(screen.getByLabelText("نوع حرکت")).toHaveValue("compound");
  expect(screen.getByLabelText("فشار داخلی شانه")).toBeChecked();
  expect(screen.getByLabelText("قابل استفاده برای تولید برنامه")).toBeChecked();

  await user.clear(screen.getByLabelText("نام انگلیسی"));
  await user.type(screen.getByLabelText("نام انگلیسی"), "Advanced Incline Push Up");
  await user.clear(screen.getByLabelText("نام فارسی"));
  await user.type(screen.getByLabelText("نام فارسی"), "شنا شیب‌دار پیشرفته");
  await user.click(screen.getByLabelText("دمبل"));
  await user.selectOptions(screen.getByLabelText("سطح سختی"), "advanced");
  await user.clear(screen.getByLabelText("مرحله انگلیسی ۱"));
  await user.type(screen.getByLabelText("مرحله انگلیسی ۱"), "Set the bench securely");
  await user.clear(screen.getByLabelText("نکته فارسی ۱"));
  await user.type(screen.getByLabelText("نکته فارسی ۱"), "شانه‌ها را ثابت نگه دارید");

  await user.selectOptions(screen.getByLabelText("الگوی حرکت"), "vertical_push");
  await user.click(screen.getByRole("button", { name: "ذخیره تغییرات" }));

  expect(adminApi.updateAdminExercise).toHaveBeenCalledWith(
    "exercise-id",
    expect.objectContaining({
      name_en: "Advanced Incline Push Up",
      name_fa: "شنا شیب‌دار پیشرفته",
      equipment: ["bodyweight", "bench", "dumbbell"],
      difficulty: "advanced",
      instructions_en: ["Set the bench securely", "Lower", "Press"],
      safety_notes_fa: ["شانه‌ها را ثابت نگه دارید"],
      movement_pattern: "vertical_push",
      is_programmable: true,
    }),
    null,
    [],
  );
  expect(await screen.findByText("LIST PAGE")).toBeInTheDocument();
});
