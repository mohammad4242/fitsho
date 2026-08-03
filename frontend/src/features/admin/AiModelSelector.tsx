import type { AdminAiCatalogModel } from "./types";
import { useTranslation } from "react-i18next";

type Props = {
  id: string;
  label: string;
  models: AdminAiCatalogModel[];
  value: string;
  onChange: (value: string) => void;
  multiple?: boolean;
  values?: string[];
  onMultipleChange?: (values: string[]) => void;
};

export function AiModelSelector({
  id,
  label,
  models,
  value,
  onChange,
  multiple = false,
  values = [],
  onMultipleChange,
}: Props) {
  const { t } = useTranslation();
  return (
    <label className="admin-ai-setting-field" htmlFor={id}>
      <span>{label}</span>
      <select
        id={id}
        multiple={multiple}
        value={multiple ? values : value}
        onChange={(event) => {
          if (multiple) {
            onMultipleChange?.(
              Array.from(event.currentTarget.selectedOptions, (option) => option.value),
            );
          } else {
            onChange(event.currentTarget.value);
          }
        }}
      >
        {!multiple && <option value="">{t("admin.aiSettings.selectModel")}</option>}
        {models.map((model) => (
          <option key={model.model_id} value={model.model_id}>
            {model.display_name} — {model.model_id}
          </option>
        ))}
      </select>
    </label>
  );
}
