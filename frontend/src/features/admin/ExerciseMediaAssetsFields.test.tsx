import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { useState, type ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { ExerciseMediaAssetsFields } from "./ExerciseMediaAssetsFields";
import type { AdminExerciseMediaAssetInput } from "./types";

describe("ExerciseMediaAssetsFields", () => {
  it("offers videos only", async () => {
    const user = userEvent.setup();
    render(
      <MediaFieldsHarness />,
    );

    await user.click(screen.getByRole("button", { name: "افزودن ویدئو" }));

    expect(screen.queryByText("نوع رسانه ۱")).not.toBeInTheDocument();
    expect(screen.getByLabelText("فایل ویدئوی ۱")).toHaveAttribute(
      "accept", "video/mp4,video/webm",
    );
  });

  it("moves a video down without changing the other gender tab", async () => {
    const user = userEvent.setup();
    render(<MediaFieldsHarness initialAssets={[
      asset("male", 0, "https://source.example/male-first.mp4"),
      asset("male", 1, "https://source.example/male-second.mp4"),
      asset("male", 2, "https://source.example/male-third.mp4"),
      asset("female", 0, "https://source.example/female-first.mp4"),
      asset("female", 1, "https://source.example/female-second.mp4"),
    ]} />);

    expect(screen.getAllByRole("button", { name: /بالا بردن ویدئو/ })[0]).toBeDisabled();
    expect(screen.getAllByRole("button", { name: /پایین بردن ویدئو/ })[2]).toBeDisabled();
    expect(screen.getAllByLabelText("پیش‌نمایش ویدئو ۱")[0]).toHaveAttribute(
      "src", "/media/male-0.mp4",
    );
    expect(screen.getAllByRole("button", { name: "پایین بردن ویدئو ۱" })[0]).toHaveStyle({
      touchAction: "manipulation",
    });
    await user.click(screen.getAllByRole("button", { name: "پایین بردن ویدئو ۱" })[0]);

    expect(screen.getAllByTestId("admin-media-asset").map((item) =>
      (item.querySelector("input[type='url']") as HTMLInputElement)?.value,
    )).toEqual([
      "https://source.example/male-second.mp4",
      "https://source.example/male-first.mp4",
      "https://source.example/male-third.mp4",
    ]);
    expect(screen.getAllByLabelText("پیش‌نمایش ویدئو ۱")[0]).toHaveAttribute(
      "src", "/media/male-1.mp4",
    );

    await user.click(screen.getByRole("tab", { name: "زن" }));
    expect(screen.getAllByTestId("admin-media-asset").map((item) =>
      (item.querySelector("input[type='url']") as HTMLInputElement)?.value,
    )).toEqual([
      "https://source.example/female-first.mp4",
      "https://source.example/female-second.mp4",
    ]);
    expect(screen.getAllByLabelText("پیش‌نمایش ویدئو ۱")[0]).toHaveAttribute(
      "src", "/media/female-0.mp4",
    );
  });
});

function MediaFieldsHarness({
  initialAssets = [],
}: {
  initialAssets?: ComponentProps<typeof ExerciseMediaAssetsFields>["assets"];
}) {
  const [assets, setAssets] = useState<ComponentProps<typeof ExerciseMediaAssetsFields>["assets"]>(initialAssets);
  const [files, setFiles] = useState<File[]>([]);
  return (
    <ExerciseMediaAssetsFields
      accordion={{
        id: "media-variants",
        title: "ویدئوهای زن و مرد",
        isOpen: true,
        onToggle: () => undefined,
      }}
      assets={assets}
      files={files}
      onAssetsChange={setAssets}
      onFilesChange={setFiles}
    />
  );
}

function asset(
  presentation: "male" | "female",
  sort_order: number,
  media_source_url: string,
): AdminExerciseMediaAssetInput {
  return {
    presentation,
    role: "video",
    sort_order,
    upload_index: null,
    media_source_url,
    media_path: `/media/${presentation}-${sort_order}.mp4`,
    media_license: null,
    media_attribution: null,
  };
}
