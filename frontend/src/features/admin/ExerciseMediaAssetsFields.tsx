import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { MediaPresentation } from "../exercises/types";
import type { AdminExerciseMediaAssetInput, AdminExerciseMediaFiles } from "./types";

type Props = {
  assets: AdminExerciseMediaAssetInput[];
  files: AdminExerciseMediaFiles;
  onAssetsChange: (assets: AdminExerciseMediaAssetInput[]) => void;
  onFilesChange: (files: AdminExerciseMediaFiles) => void;
};

function nextSortOrder(
  assets: AdminExerciseMediaAssetInput[],
  presentation: MediaPresentation,
): number {
  return Math.max(
    -1,
    ...assets
      .filter((asset) => asset.presentation === presentation)
      .map((asset) => asset.sort_order),
  ) + 1;
}

export function ExerciseMediaAssetsFields({ assets, files, onAssetsChange, onFilesChange }: Props) {
  const { t } = useTranslation();
  const [presentation, setPresentation] = useState<"male" | "female">("male");
  const visible = assets.filter((asset) => asset.presentation === presentation);

  function addAsset() {
    onAssetsChange([...assets, {
      presentation,
      role: "video",
      sort_order: nextSortOrder(assets, presentation),
      upload_index: null,
      media_source_url: null,
      media_license: null,
      media_attribution: null,
    }]);
  }

  function change(index: number, patch: Partial<AdminExerciseMediaAssetInput>) {
    onAssetsChange(assets.map((asset) => asset === visible[index] ? { ...asset, ...patch } : asset));
  }

  function remove(index: number) {
    const asset = visible[index];
    const next = assets.filter((item) => item !== asset);
    if (asset.upload_index !== null && asset.upload_index !== undefined) {
      onFilesChange(files.filter((_, fileIndex) => fileIndex !== asset.upload_index));
      onAssetsChange(next.map((item) => (
        item.upload_index !== null && item.upload_index !== undefined && item.upload_index > asset.upload_index!
          ? { ...item, upload_index: item.upload_index - 1 }
          : item
      )));
      return;
    }
    onAssetsChange(next);
  }

  function changeFile(index: number, file: File | null) {
    if (file === null) return;
    const asset = visible[index];
    const uploadIndex = asset.upload_index ?? files.length;
    const nextFiles = [...files];
    nextFiles[uploadIndex] = file;
    onFilesChange(nextFiles);
    onAssetsChange(assets.map((item) => item === asset ? { ...item, upload_index: uploadIndex } : item));
  }

  return <fieldset className="admin-form-section"><legend>{t("admin.fields.mediaVariants")}</legend>
    <div className="admin-media-tabs" role="tablist" aria-label={t("admin.fields.mediaVariants")}>
      <button type="button" role="tab" aria-selected={presentation === "male"} onClick={() => setPresentation("male")}>{t("admin.fields.male")}</button>
      <button type="button" role="tab" aria-selected={presentation === "female"} onClick={() => setPresentation("female")}>{t("admin.fields.female")}</button>
    </div>
    <div className="admin-media-assets">{visible.map((asset, index) => {
      const number = (index + 1).toLocaleString("fa-IR");
      const fileId = `media-${asset.presentation}-${asset.sort_order}`;
      return <section className="admin-media-asset" key={fileId}>
        <div className="admin-media-asset__header">
          <strong>{t("admin.fields.mediaItem", { number })}</strong>
          <button type="button" className="admin-media-remove" onClick={() => remove(index)}>{t("admin.fields.removeMedia")}</button>
        </div>
        <label htmlFor={`${fileId}-file`}>{t("admin.fields.galleryMediaFile", { number })}</label>
        <input id={`${fileId}-file`} accept="video/mp4,video/webm" type="file" onChange={(event) => changeFile(index, event.target.files?.[0] ?? null)} />
        <small>{asset.upload_index === null || asset.upload_index === undefined ? t("admin.fields.existingFile") : files[asset.upload_index]?.name}</small>
        <details>
          <summary>{t("admin.fields.sourceDetails")}</summary>
          <label htmlFor={`${fileId}-source`}>{t("admin.fields.sourceUrl")}</label>
          <input id={`${fileId}-source`} dir="ltr" type="url" value={asset.media_source_url ?? ""} onChange={(event) => change(index, { media_source_url: event.target.value })} />
          <label htmlFor={`${fileId}-license`}>{t("admin.fields.license")}</label>
          <input id={`${fileId}-license`} value={asset.media_license ?? ""} onChange={(event) => change(index, { media_license: event.target.value })} />
          <label htmlFor={`${fileId}-attribution`}>{t("admin.fields.attribution")}</label>
          <input id={`${fileId}-attribution`} value={asset.media_attribution ?? ""} onChange={(event) => change(index, { media_attribution: event.target.value })} />
        </details>
      </section>;
    })}</div>
    <button type="button" className="admin-media-add" onClick={addAsset}>{t("admin.fields.addMedia")}</button>
  </fieldset>;
}
