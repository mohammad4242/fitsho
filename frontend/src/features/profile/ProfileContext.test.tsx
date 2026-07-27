import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { useAuth } from "../auth/AuthContext";
import type { User } from "../auth/types";
import * as api from "./api";
import { ProfileProvider, useProfile } from "./ProfileContext";
import type { Profile, ProfileInput } from "./types";

vi.mock("../auth/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("./api", () => ({
  getProfile: vi.fn(),
  createProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

const user: User = {
  id: "018f0000-0000-7000-8000-000000000001",
  email: "member@example.com",
  created_at: "2026-07-24T00:00:00Z",
};

const profileInput: ProfileInput = {
  display_name: "Mohammad",
  birth_date: "2000-05-14",
  sex: "male",
  height_cm: 178,
  current_weight_kg: 76.5,
  fitness_goal: "build_muscle",
  experience_level: "beginner",
  training_days_per_week: 3,
  training_location: "gym",
  home_training_setup: null,
  session_duration_minutes: 60,
  physical_limitations: null,
};

const profile: Profile = {
  ...profileInput,
  user_id: user.id,
  weight_measured_at: "2026-07-27T10:30:00Z",
  created_at: "2026-07-27T10:30:00Z",
  updated_at: "2026-07-27T10:30:00Z",
};

let authUser: User | null;

beforeEach(() => {
  vi.clearAllMocks();
  authUser = null;
  vi.mocked(useAuth).mockImplementation(() => ({
    user: authUser,
    loading: false,
    startupError: false,
    retryStartup: vi.fn(),
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  }));
});

function Probe() {
  const {
    status,
    profile: currentProfile,
    retryProfile,
    createProfile,
    updateProfile,
  } = useProfile();

  return (
    <div>
      <span>status:{status}</span>
      <span>name:{currentProfile?.display_name ?? "none"}</span>
      <button type="button" onClick={retryProfile}>
        retry
      </button>
      <button
        type="button"
        onClick={() => void createProfile(profileInput).catch(() => undefined)}
      >
        create
      </button>
      <button
        type="button"
        onClick={() =>
          void updateProfile({ display_name: "Updated" }).catch(() => undefined)
        }
      >
        update
      </button>
    </div>
  );
}

function renderProfile() {
  return render(
    <ProfileProvider>
      <Probe />
    </ProfileProvider>,
  );
}

it("stays idle and skips profile loading for a guest", () => {
  renderProfile();

  expect(screen.getByText("status:idle")).toBeInTheDocument();
  expect(api.getProfile).not.toHaveBeenCalled();
});

it("loads the authenticated user profile", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(profile);

  renderProfile();

  expect(screen.getByText("status:loading")).toBeInTheDocument();
  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  expect(screen.getByText("name:Mohammad")).toBeInTheDocument();
});

it("marks an authenticated user without a profile as missing", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(null);

  renderProfile();

  expect(await screen.findByText("status:missing")).toBeInTheDocument();
});

it("keeps startup failures separate from a missing profile", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockRejectedValue(new Error("offline"));

  renderProfile();

  expect(await screen.findByText("status:error")).toBeInTheDocument();
  expect(screen.queryByText("status:missing")).not.toBeInTheDocument();
});

it("retries profile loading after an error", async () => {
  authUser = user;
  vi.mocked(api.getProfile)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(profile);
  const browserUser = userEvent.setup();

  renderProfile();
  expect(await screen.findByText("status:error")).toBeInTheDocument();
  await browserUser.click(screen.getByRole("button", { name: "retry" }));

  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  expect(api.getProfile).toHaveBeenCalledTimes(2);
});

it("stores a successfully created profile", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(null);
  vi.mocked(api.createProfile).mockResolvedValue(profile);
  const browserUser = userEvent.setup();

  renderProfile();
  expect(await screen.findByText("status:missing")).toBeInTheDocument();
  await browserUser.click(screen.getByRole("button", { name: "create" }));

  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  expect(screen.getByText("name:Mohammad")).toBeInTheDocument();
});

it("leaves a missing profile missing when creation fails", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(null);
  vi.mocked(api.createProfile).mockRejectedValue(new Error("offline"));
  const browserUser = userEvent.setup();

  renderProfile();
  expect(await screen.findByText("status:missing")).toBeInTheDocument();
  await browserUser.click(screen.getByRole("button", { name: "create" }));

  await waitFor(() => expect(api.createProfile).toHaveBeenCalledWith(profileInput));
  expect(screen.getByText("status:missing")).toBeInTheDocument();
});

it("stores a successfully updated profile", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(profile);
  vi.mocked(api.updateProfile).mockResolvedValue({
    ...profile,
    display_name: "Updated",
  });
  const browserUser = userEvent.setup();

  renderProfile();
  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  await browserUser.click(screen.getByRole("button", { name: "update" }));

  expect(await screen.findByText("name:Updated")).toBeInTheDocument();
});

it("keeps the current profile ready when an update fails", async () => {
  authUser = user;
  vi.mocked(api.getProfile).mockResolvedValue(profile);
  vi.mocked(api.updateProfile).mockRejectedValue(new Error("offline"));
  const browserUser = userEvent.setup();

  renderProfile();
  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  await browserUser.click(screen.getByRole("button", { name: "update" }));

  await waitFor(() =>
    expect(api.updateProfile).toHaveBeenCalledWith({ display_name: "Updated" }),
  );
  expect(screen.getByText("status:ready")).toBeInTheDocument();
  expect(screen.getByText("name:Mohammad")).toBeInTheDocument();
});

it("ignores a stale profile response after logout", async () => {
  authUser = user;
  let resolveProfile: (value: Profile | null) => void = () => undefined;
  vi.mocked(api.getProfile).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveProfile = resolve;
      }),
  );
  const view = renderProfile();
  expect(screen.getByText("status:loading")).toBeInTheDocument();

  authUser = null;
  view.rerender(
    <ProfileProvider>
      <Probe />
    </ProfileProvider>,
  );
  expect(await screen.findByText("status:idle")).toBeInTheDocument();

  await act(async () => resolveProfile(profile));

  expect(screen.getByText("status:idle")).toBeInTheDocument();
  expect(screen.getByText("name:none")).toBeInTheDocument();
});

it("does not let a stale startup response overwrite profile creation", async () => {
  authUser = user;
  let resolveProfile: (value: Profile | null) => void = () => undefined;
  vi.mocked(api.getProfile).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveProfile = resolve;
      }),
  );
  vi.mocked(api.createProfile).mockResolvedValue(profile);
  const browserUser = userEvent.setup();
  renderProfile();
  expect(screen.getByText("status:loading")).toBeInTheDocument();

  await browserUser.click(screen.getByRole("button", { name: "create" }));
  expect(await screen.findByText("status:ready")).toBeInTheDocument();
  await act(async () => resolveProfile(null));

  expect(screen.getByText("status:ready")).toBeInTheDocument();
  expect(screen.getByText("name:Mohammad")).toBeInTheDocument();
});
