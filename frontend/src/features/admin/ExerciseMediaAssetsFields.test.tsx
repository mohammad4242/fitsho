import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { useState, type ComponentProps } from "react";
import { describe, expect, it } from "vitest";

import { ExerciseMediaAssetsFields } from "./ExerciseMediaAssetsFields";

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
});

function MediaFieldsHarness() {
  const [assets, setAssets] = useState<ComponentProps<typeof ExerciseMediaAssetsFields>["assets"]>([]);
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
