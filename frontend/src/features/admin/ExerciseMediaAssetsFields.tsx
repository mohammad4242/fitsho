import { useTranslation } from "react-i18next";

import type {
  AdminExerciseMediaAssetInput,
  AdminExerciseMediaFiles,
  MediaAssetKey,
} from "./types";

type AssetDefinition = {
  key: MediaAssetKey;
  presentation: AdminExerciseMediaAssetInput["presentation"];
  role: AdminExerciseMediaAssetInput["role"];
  accept: string;
  labelKey: "maleVideo" | "femaleVideo" | "maleThumbnail" | "femaleThumbnail";
};

const assetDefinitions: readonly AssetDefinition[] = [
  { key: "male_video", presentation: "male", role: "video", accept: "video/mp4,video/webm", labelKey: "maleVideo" },
  { key: "female_video", presentation: "female", role: "video", accept: "video/mp4,video/webm", labelKey: "femaleVideo" },
  { key: "male_thumbnail", presentation: "male", role: "thumbnail", accept: "image/jpeg", labelKey: "maleThumbnail" },
  { key: "female_thumbnail", presentation: "female", role: "thumbnail", accept: "image/jpeg", labelKey: "femaleThumbnail" },
];

type Props = {
  assets: AdminExerciseMediaAssetInput[];
  files: AdminExerciseMediaFiles;
  retainMetadataWithoutFile: boolean;
  onAssetsChange: (assets: AdminExerciseMediaAssetInput[]) => void;
  onFilesChange: (files: AdminExerciseMediaFiles) => void;
};

export function ExerciseMediaAssetsFields({
  assets,
  files,
  retainMetadataWithoutFile,
  onAssetsChange,
  onFilesChange,
}: Props) {
  const { t } = useTranslation();

  function findAsset(definition: AssetDefinition) {
    return assets.find(
      (asset) => asset.presentation === definition.presentation && asset.role === definition.role,
    );
  }

  function ensureAsset(definition: AssetDefinition) {
    return findAsset(definition) ?? {
      presentation: definition.presentation,
      role: definition.role,
      media_source_url: null,
      media_license: null,
      media_attribution: null,
    };
  }

  function changeFile(definition: AssetDefinition, file: File | null) {
    const nextFiles = { ...files };
    if (file === null) delete nextFiles[definition.key];
    else nextFiles[definition.key] = file;
    onFilesChange(nextFiles);
    if (file !== null && findAsset(definition) === undefined) {
      onAssetsChange([...assets, ensureAsset(definition)]);
    }
    if (file === null && !retainMetadataWithoutFile) {
      onAssetsChange(
        assets.filter(
          (asset) => asset.presentation !== definition.presentation || asset.role !== definition.role,
        ),
      );
    }
  }

  function changeMetadata(
    definition: AssetDefinition,
    field: "media_source_url" | "media_license" | "media_attribution",
    value: string,
  ) {
    const current = ensureAsset(definition);
    const next = { ...current, [field]: value || null };
    onAssetsChange([
      ...assets.filter(
        (asset) => asset.presentation !== definition.presentation || asset.role !== definition.role,
      ),
      next,
    ]);
  }

  return (
    <fieldset className="admin-form-section">
      <legend>{t("admin.fields.mediaVariants")}</legend>
      <div className="admin-media-assets">
        {assetDefinitions.map((definition) => {
          const asset = findAsset(definition);
          const label = t(`admin.fields.${definition.labelKey}`);
          return (
            <section className="admin-media-asset" key={definition.key}>
              <h2>{label}</h2>
              <label>
                {label}
                <input
                  accept={definition.accept}
                  type="file"
                  onChange={(event) => changeFile(definition, event.target.files?.[0] ?? null)}
                />
              </label>
              {asset !== undefined && (
                <div className="admin-field-grid">
                  <label>
                    {t("admin.fields.sourceUrl")}
                    <input
                      dir="ltr"
                      type="url"
                      value={asset.media_source_url ?? ""}
                      onChange={(event) => changeMetadata(definition, "media_source_url", event.target.value)}
                    />
                  </label>
                  <label>
                    {t("admin.fields.license")}
                    <input
                      value={asset.media_license ?? ""}
                      onChange={(event) => changeMetadata(definition, "media_license", event.target.value)}
                    />
                  </label>
                  <label>
                    {t("admin.fields.attribution")}
                    <input
                      value={asset.media_attribution ?? ""}
                      onChange={(event) => changeMetadata(definition, "media_attribution", event.target.value)}
                    />
                  </label>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </fieldset>
  );
}
