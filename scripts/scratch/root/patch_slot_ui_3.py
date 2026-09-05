import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "r") as f:
    content = f.read()

# I will find the end of the slot grid and append the remove/details action there.
# The end of the slot grid is `onChange={(value) => patchSlot(dayIndex, slotIndex, { target_muscles: parseMuscles(value) })} />\n                                      </div>`

slot_end_regex = r'(onChange=\{\(value\) => patchSlot\(dayIndex, slotIndex, \{ target_muscles: parseMuscles\(value\) \}\)\} />\n\s*</div>)'

actions_buttons = """                                      <div className="admin-template-editor-slot__actions-footer" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
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
                                          style={{ color: 'var(--fitsho-destructive)', background: 'none', border: 'none', cursor: 'pointer' }}
                                        >
                                          {t("admin.templateEditor.removeExercise")}
                                        </button>
                                      </div>"""

content = re.sub(slot_end_regex, r'\1\n' + actions_buttons, content)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)
