import re

with open("backend/app/training_templates/models.py", "r") as f:
    content = f.read()

# Add new columns to TrainingProgramTemplateSlot
new_columns = """    superset_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    superset_exercise_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("exercises.id", ondelete="SET NULL"), nullable=True, index=True
    )
    superset_exercise_slug_hint: Mapped[str | None] = mapped_column(String(120), nullable=True)
"""
content = re.sub(r'    superset_group: Mapped\[str \| None\] = mapped_column\(String\(32\), nullable=True\)\n', new_columns, content)

# Add superset_exercise relationship
new_relationship = """    exercise: Mapped[Exercise | None] = relationship(foreign_keys=[exercise_id])
    superset_exercise: Mapped[Exercise | None] = relationship(foreign_keys=[superset_exercise_id])"""
content = re.sub(r'    exercise: Mapped\[Exercise \| None\] = relationship\(\)', new_relationship, content)

# Add constraints
new_constraints = """        CheckConstraint(
            "rest_seconds BETWEEN 0 AND 600", name="ck_training_program_template_slots_rest"
        ),
        CheckConstraint(
            "(intensity_method = 'superset' AND superset_exercise_id IS NOT NULL AND exercise_id != superset_exercise_id AND superset_exercise_slug_hint IS NOT NULL) OR (intensity_method != 'superset' AND superset_exercise_id IS NULL AND superset_exercise_slug_hint IS NULL)",
            name="ck_training_program_template_slots_superset_validity"
        ),"""
content = re.sub(r'        CheckConstraint\(\n            "rest_seconds BETWEEN 0 AND 600", name="ck_training_program_template_slots_rest"\n        \),', new_constraints, content)

with open("backend/app/training_templates/models.py", "w") as f:
    f.write(content)
