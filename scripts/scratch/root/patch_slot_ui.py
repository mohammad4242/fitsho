import re

with open("/tmp/editor_step1.tsx", "r") as f:
    content = f.read()

# 1. Add Draft Slot button
old_add_btn = r'<button className="admin-template-editor-add" onClick=\{\(\) => setPickerTarget\(\{ dayIndex, slotIndex: null \}\)\} type="button">\{t\("admin.templateEditor.addExercise"\)\}</button>'
new_add_btn = r'<button className="admin-template-editor-add" onClick={() => addDraftSlot(dayIndex)} type="button">{t("admin.templateEditor.addExercise")}</button>'
content = re.sub(old_add_btn, new_add_btn, content)

# 2. Update the header
old_header = r'<span className="admin-template-editor-slot__index">\{slotIndex \+ 1\}</span>\s*<strong className="admin-template-editor-slot__title">\{slotName\}</strong>'
new_header = """<span className="admin-template-editor-slot__index">{slotIndex + 1}</span>
                                        {slot.intensity_method === "superset" ? (
                                          <div className="admin-template-editor-slot__title">
                                            <span className="admin-badge admin-badge--superset">{t("admin.templates.methods.superset")}</span>
                                            <div>A. {slot.exercise_name_fa || "?"}</div>
                                            <div>B. {slot.superset_exercise_name_fa || "?"}</div>
                                          </div>
                                        ) : (
                                          <strong className="admin-template-editor-slot__title">
                                            {slot.intensity_method === "drop_set" && <span className="admin-badge admin-badge--drop-set">{t("admin.templates.methods.drop_set")} </span>}
                                            {slotName}
                                          </strong>
                                        )}"""
content = re.sub(old_header, new_header, content)

# 3. Update the panel actions and grid
old_panel = r'<div className="admin-template-editor-slot__actions">[\s\S]*?<label className="admin-field">\s*<span>\{t\("admin\.templateEditor\.method"\)\}</span>\s*<select value=\{slot\.intensity_method\} onChange=\{\(event\) => patchSlot\(dayIndex, slotIndex, \{ intensity_method: event\.target\.value as TrainingTemplateMethod \}\)\}>\s*\{methods\.map\(\(method\) => <option key=\{method\} value=\{method\}>\{t\(`admin\.templates\.methods\.\$\{method\}`\)\}</option>\)\}\s*</select>\s*</label>'

new_panel = """<div className="admin-template-editor-grid admin-template-editor-grid--slot">
                                        <div className="admin-field admin-field--full-width">
                                          <span>{t("admin.templateEditor.executionMethod")}</span>
                                          <div className="admin-method-selector">
                                            {methods.map((method) => (
                                              <label key={method}>
                                                <input
                                                  type="radio"
                                                  name={`method-${slotKey}`}
                                                  value={method}
                                                  checked={slot.intensity_method === method}
                                                  onChange={(e) => {
                                                    const newMethod = e.target.value as TrainingTemplateMethod;
                                                    if (newMethod === "standard" || newMethod === "drop_set") {
                                                      patchSlot(dayIndex, slotIndex, {
                                                        intensity_method: newMethod,
                                                        superset_exercise_id: null,
                                                        superset_exercise_name_fa: null,
                                                        superset_exercise_name_en: null,
                                                        superset_exercise_slug: null,
                                                      });
                                                    } else {
                                                      patchSlot(dayIndex, slotIndex, {
                                                        intensity_method: newMethod,
                                                      });
                                                    }
                                                  }}
                                                />
                                                {t(`admin.templates.methods.${method}`)}
                                              </label>
                                            ))}
                                          </div>
                                        </div>

                                        <div className="admin-field admin-field--full-width">
                                          <span>{slot.intensity_method === "superset" ? t("admin.templateEditor.movement1") : t("admin.templateEditor.movement")}</span>
                                          <div className="admin-slot-picker-group">
                                            <strong>{slot.exercise_name_fa || t("admin.templateEditor.emptyMovement")}</strong>
                                            <button type="button" onClick={() => setPickerTarget({ dayIndex, slotIndex, member: "primary" })}>
                                              {t("admin.templateEditor.chooseFromLibrary")}
                                            </button>
                                          </div>
                                        </div>

                                        {slot.intensity_method === "superset" && (
                                          <div className="admin-field admin-field--full-width">
                                            <span>{t("admin.templateEditor.movement2")}</span>
                                            <div className="admin-slot-picker-group">
                                              <strong>{slot.superset_exercise_name_fa || t("admin.templateEditor.emptyMovement")}</strong>
                                              <button type="button" onClick={() => setPickerTarget({ dayIndex, slotIndex, member: "superset" })}>
                                                {t("admin.templateEditor.chooseFromLibrary")}
                                              </button>
                                            </div>
                                          </div>
                                        )}

                                        <TextInput
                                          dir="rtl"
                                          label={t("admin.templateEditor.displayNameFa")}
                                          placeholder={baseNameFa || undefined}
                                          value={slot.display_name_fa ?? ""}
                                          onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_fa: value || null })}
                                        />
                                        <TextInput
                                          dir="ltr"
                                          label={t("admin.templateEditor.displayNameEn")}
                                          placeholder={baseNameEn || undefined}
                                          value={slot.display_name_en ?? ""}
                                          onChange={(value) => patchSlot(dayIndex, slotIndex, { display_name_en: value || null })}
                                        />
                                        <NumberInput label={t("admin.templateEditor.sets")} value={slot.sets} onChange={(value) => patchSlot(dayIndex, slotIndex, { sets: value })} />
                                        <NumberInput label={t("admin.templateEditor.repMin")} value={slot.rep_min} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_min: value })} />
                                        <NumberInput label={t("admin.templateEditor.repMax")} value={slot.rep_max} onChange={(value) => patchSlot(dayIndex, slotIndex, { rep_max: value })} />
                                        <NumberInput label={t("admin.templateEditor.rir")} value={slot.target_rir} onChange={(value) => patchSlot(dayIndex, slotIndex, { target_rir: value })} />
                                        <NumberInput label={t("admin.templateEditor.rest")} value={slot.rest_seconds} onChange={(value) => patchSlot(dayIndex, slotIndex, { rest_seconds: value })} />
"""

content = re.sub(old_panel, new_panel, content)

# 4. Remove button should be moved below or put into a small actions div at the bottom of panel
old_actions_end = r'(<label className="admin-field">\s*<span>\{t\("admin\.templateEditor\.priority"\)\}</span>)'
new_actions_end = r"""\1"""
content = re.sub(old_actions_end, new_actions_end, content)

# I forgot the remove/details buttons. I will add them at the bottom of the grid.
actions_buttons = """
                                        <div className="admin-template-editor-slot__actions-footer">
                                          {slot.exercise_id && (
                                              <Link to={`/admin/exercises/${slot.exercise_id}/edit`}>
                                                {t("admin.templateEditor.exerciseDetails")} ↗
                                              </Link>
                                          )}
                                          <button
                                            aria-label={t("admin.templateEditor.removeExerciseAria", { name: slotName })}
                                            onClick={() => removeSlot(dayIndex, slotIndex)}
                                            type="button"
                                            className="admin-slot-remove-btn"
                                          >
                                            {t("admin.templateEditor.removeExercise")}
                                          </button>
                                        </div>
"""
content = re.sub(r'(</select>\s*</label>\s*</div>\s*</div>\s*)}', r'\1' + actions_buttons + r'</div>\n                                  )}', content)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)
