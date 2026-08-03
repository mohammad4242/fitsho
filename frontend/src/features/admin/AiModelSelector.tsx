import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { AdminAiCatalogModel } from "./types";

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
  const [search, setSearch] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const labelId = `${id}-label`;
  const listboxId = `${id}-options`;
  const visibleModels = models.filter((model) => {
    const term = search.trim().toLocaleLowerCase();
    return !term || `${model.display_name} ${model.model_id}`.toLocaleLowerCase().includes(term);
  });
  const selectedModel = models.find((model) => model.model_id === value);
  const selectionLabel = multiple
    ? values.length > 0
      ? t("admin.aiSettings.selectedModels", { count: values.length })
      : t("admin.aiSettings.selectModel")
    : selectedModel
      ? `${selectedModel.display_name} — ${selectedModel.model_id}`
      : t("admin.aiSettings.selectModel");

  useEffect(() => {
    if (isOpen) searchRef.current?.focus();
  }, [isOpen]);

  function chooseModel(modelId: string) {
    if (multiple) {
      const next = values.includes(modelId)
        ? values.filter((selectedId) => selectedId !== modelId)
        : [...values, modelId];
      onMultipleChange?.(next);
      return;
    }
    onChange(modelId);
    setSearch("");
    setIsOpen(false);
  }

  return (
    <div className="admin-ai-setting-field">
      <span id={labelId}>{label}</span>
      <div className="admin-ai-model-selector">
        <button
          id={id}
          type="button"
          className="admin-ai-model-selector__trigger"
          role="combobox"
          aria-labelledby={labelId}
          aria-controls={listboxId}
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
        >
          <span>{selectionLabel}</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5" /></svg>
        </button>
        {isOpen && (
          <div className="admin-ai-model-selector__menu">
            <input
              ref={searchRef}
              aria-label={`${label} search`}
              type="search"
              value={search}
              placeholder={t("admin.aiSettings.searchModels")}
              onChange={(event) => setSearch(event.currentTarget.value)}
            />
            <div id={listboxId} className="admin-ai-model-selector__options" role="listbox" aria-label={label} aria-multiselectable={multiple || undefined}>
              {visibleModels.map((model) => {
                const selected = multiple ? values.includes(model.model_id) : model.model_id === value;
                return (
                  <button
                    key={model.model_id}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    onClick={() => chooseModel(model.model_id)}
                  >
                    <strong>{model.display_name}</strong>
                    <small>{model.model_id}</small>
                  </button>
                );
              })}
              {visibleModels.length === 0 && <p>{t("admin.aiSettings.noMatchingModels")}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
