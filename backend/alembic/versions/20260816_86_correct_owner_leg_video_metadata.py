"""correct six owner videos that were classified as forearm exercises"""

from __future__ import annotations

import json
from collections.abc import Sequence
from copy import deepcopy

import sqlalchemy as sa

from alembic import op
from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)

revision: str = "20260816_86"
down_revision: str | Sequence[str] | None = "20260816_85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CORRECTIONS: dict[str, dict[str, object]] = {
    "35889cc979dbaa7b11f910d20a107832c1bda537f426d5a8f912efb75c925908": {
        "name_en": "Landmine Squat",
        "name_fa": "اسکوات لندماین",
        "primary_muscle": MuscleGroup.LEGS,
        "movement_pattern": MovementPattern.SQUAT,
        "equipment": (Equipment.OTHER,),
        "caution_tags": (
            ExerciseCautionTag.DEEP_KNEE_FLEXION,
            ExerciseCautionTag.LOWER_BACK_LOADING,
        ),
        "video_label_en": "landmine squat",
        "video_label_fa": "اسکوات لندماین",
    },
    "3be618aac4fed3a795d09a8737f6d24d91ea8163e22973c12d01672de5901ae7": {
        "name_en": "Split Squat",
        "name_fa": "اسپلیت اسکوات",
        "primary_muscle": MuscleGroup.LEGS,
        "movement_pattern": MovementPattern.LUNGE,
        "equipment": (Equipment.OTHER,),
        "caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION, ExerciseCautionTag.BALANCE_DEMAND),
        "video_label_en": "split squat",
        "video_label_fa": "اسپلیت اسکوات",
    },
    "f20d44173274d17b351db5066edd8096810572211023b1c8e3ea10f18516d05f": {
        "name_en": "Leg Press - Quads",
        "name_fa": "پرس پا - چهارسر",
        "primary_muscle": MuscleGroup.QUADRICEPS,
        "movement_pattern": MovementPattern.SQUAT,
        "equipment": (Equipment.MACHINE,),
        "caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
        "video_label_en": "quads",
        "video_label_fa": "چهارسر",
    },
    "157b4670b7d3685c85fc834e6cb82550663cd6f84140318100515596064e8127": {
        "name_en": "Leg Press - Vastus Lateralis",
        "name_fa": "پرس پا - پهن خارجی چهارسر",
        "primary_muscle": MuscleGroup.QUADRICEPS,
        "movement_pattern": MovementPattern.SQUAT,
        "equipment": (Equipment.MACHINE,),
        "caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
        "video_label_en": "vastus lateralis",
        "video_label_fa": "پهن خارجی چهارسر",
    },
    "0583f6d60222523f45f9e9eb226f37ac2bba3a3162aab1627bee50c1706c0b4d": {
        "name_en": "Leg Press - Quadriceps",
        "name_fa": "پرس پا - چهارسر ران",
        "primary_muscle": MuscleGroup.QUADRICEPS,
        "movement_pattern": MovementPattern.SQUAT,
        "equipment": (Equipment.MACHINE,),
        "caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
        "video_label_en": "quads",
        "video_label_fa": "چهارسر",
    },
    "4169deae978152bbf0bc5ebc188a861397d5ba1fb5dc9b23bf9096544324d8bb": {
        "name_en": "Leg Press - Front Quads",
        "name_fa": "پرس پا - بخش جلویی چهارسر",
        "primary_muscle": MuscleGroup.QUADRICEPS,
        "movement_pattern": MovementPattern.SQUAT,
        "equipment": (Equipment.MACHINE,),
        "caution_tags": (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
        "video_label_en": "front quads",
        "video_label_fa": "بخش جلویی چهارسر",
    },
}

_INSTRUCTIONS_EN = {
    "leg_press": (
        "Set your feet on the leg-press platform and keep your back supported.",
        "Lower the platform with control while keeping your knees aligned with your feet.",
        "Press through the whole foot without locking the knees.",
    ),
    "landmine_squat": (
        "Hold the landmine bar close to your chest and stand with your feet stable.",
        "Sit down and back while keeping your chest controlled and your knees aligned.",
        "Drive through the whole foot to return to standing.",
    ),
    "split_squat": (
        "Take a stable split stance and keep most of your weight over the working leg.",
        "Lower under control until both knees bend while keeping the front knee aligned.",
        "Push through the front foot to return without losing your stance.",
    ),
}
_INSTRUCTIONS_FA = {
    "leg_press": (
        "پاها را روی صفحهٔ دستگاه پرس پا قرار دهید و پشت را به پشتی تکیه دهید.",
        "صفحه را کنترل‌شده پایین بیاورید و زانوها را هم‌راستا با پنجه‌ها نگه دارید.",
        "با فشار از کل کف پا صفحه را بالا ببرید و زانوها را قفل نکنید.",
    ),
    "landmine_squat": (
        "میلهٔ لندماین را نزدیک سینه نگه دارید و پاها را در وضعیت پایدار قرار دهید.",
        "با کنترل به پایین و عقب بنشینید و زانوها را هم‌راستا با پنجه‌ها نگه دارید.",
        "با فشار از کل کف پا به وضعیت ایستاده برگردید.",
    ),
    "split_squat": (
        "در حالت گام‌جلو پایدار بایستید و بیشتر وزن را روی پای فعال نگه دارید.",
        "کنترل‌شده پایین بروید تا هر دو زانو خم شوند و زانوی جلو هم‌راستا بماند.",
        "با فشار از پای جلو به وضعیت شروع برگردید و حالت پاها را حفظ کنید.",
    ),
}


def _movement_kind(correction: dict[str, object]) -> str:
    if correction["movement_pattern"] is MovementPattern.LUNGE:
        return "split_squat"
    if correction["equipment"] == (Equipment.MACHINE,):
        return "leg_press"
    return "landmine_squat"


def _metadata_for_update(
    existing: object,
    source_id: str,
    correction: dict[str, object],
) -> str:
    metadata = deepcopy(existing) if isinstance(existing, dict) else {}
    analysis = metadata.get("owner_video_analysis")
    analysis = deepcopy(analysis) if isinstance(analysis, dict) else {}
    analysis.update(
        {
            "source_id": source_id,
            "name_en": correction["name_en"],
            "name_fa": correction["name_fa"],
            "body_region": "lower_body",
            "primary_muscle": correction["primary_muscle"].value,
            "muscle_focus": None,
            "secondary_muscles": [],
            "equipment": [item.value for item in correction["equipment"]],
            "difficulty": Difficulty.INTERMEDIATE.value,
            "movement_pattern": correction["movement_pattern"].value,
            "exercise_type": ExerciseType.COMPOUND.value,
            "caution_tags": [item.value for item in correction["caution_tags"]],
            "decision": "approved",
            "identification_confidence": 1.0,
            "match_confidence": 1.0,
            "review_reasons": [],
            "manual_visual_review": True,
            "video_label_en": correction["video_label_en"],
            "video_label_fa": correction["video_label_fa"],
        }
    )
    metadata["owner_video_analysis"] = analysis
    metadata["review_reasons"] = []
    return json.dumps(metadata, ensure_ascii=False)


def _update_associations(
    connection: sa.Connection,
    exercise_id: object,
    correction: dict[str, object],
) -> None:
    for table_name in (
        "exercise_secondary_muscles",
        "exercise_equipment",
        "exercise_caution_tags",
        "exercise_label_items",
    ):
        connection.execute(
            sa.text(f"DELETE FROM {table_name} WHERE exercise_id = :exercise_id"),
            {"exercise_id": exercise_id},
        )

    for table_name, value_column, values in (
        ("exercise_equipment", "equipment", correction["equipment"]),
        ("exercise_caution_tags", "caution_tag", correction["caution_tags"]),
    ):
        for value in values:
            connection.execute(
                sa.text(
                    f"INSERT INTO {table_name} (exercise_id, {value_column}) "
                    "VALUES (:exercise_id, :value)"
                ),
                {"exercise_id": exercise_id, "value": value.value},
            )


def upgrade() -> None:
    connection = op.get_bind()
    rows_by_source_id = {}
    missing_source_ids = []
    for source_id in CORRECTIONS:
        row = connection.execute(
            sa.text(
                "SELECT id, source_metadata_en FROM exercises "
                "WHERE source = 'owner-video' AND source_id = :source_id"
            ),
            {"source_id": source_id},
        ).mappings().first()
        if row is None:
            missing_source_ids.append(source_id)
            continue
        rows_by_source_id[source_id] = row

    if not rows_by_source_id:
        return
    if missing_source_ids:
        missing = ", ".join(missing_source_ids)
        raise RuntimeError(f"Missing owner-video exercises for source_id(s)={missing}")

    for source_id, correction in CORRECTIONS.items():
        row = rows_by_source_id[source_id]

        kind = _movement_kind(correction)
        connection.execute(
            sa.text(
                "UPDATE exercises SET name_en = :name_en, name_fa = :name_fa, "
                "body_region = 'lower_body', primary_muscle = :primary_muscle, "
                "muscle_focus = NULL, difficulty = :difficulty, "
                "movement_pattern = :movement_pattern, exercise_type = 'compound', "
                "instructions_en = CAST(:instructions_en AS json), "
                "instructions_fa = CAST(:instructions_fa AS json), "
                "safety_notes_en = CAST(:safety_notes_en AS json), "
                "safety_notes_fa = CAST(:safety_notes_fa AS json), "
                "short_description_en = :short_description_en, "
                "steps_en = CAST(:steps_en AS json), form_cues_en = CAST(:form_cues_en AS json), "
                "common_mistakes_en = CAST(:common_mistakes_en AS json), "
                "breathing_en = :breathing_en, "
                "source_metadata_en = CAST(:source_metadata_en AS json), "
                "needs_review = FALSE, is_programmable = TRUE "
                "WHERE id = :id"
            ),
            {
                "id": row["id"],
                "name_en": correction["name_en"],
                "name_fa": correction["name_fa"],
                "primary_muscle": correction["primary_muscle"].value,
                "difficulty": Difficulty.INTERMEDIATE.value,
                "movement_pattern": correction["movement_pattern"].value,
                "instructions_en": json.dumps(_INSTRUCTIONS_EN[kind], ensure_ascii=False),
                "instructions_fa": json.dumps(_INSTRUCTIONS_FA[kind], ensure_ascii=False),
                "safety_notes_en": json.dumps(
                    [
                        "Use a controlled range of motion and keep the knees aligned.",
                        "Stop if the position causes sharp pain or loss of control.",
                    ],
                    ensure_ascii=False,
                ),
                "safety_notes_fa": json.dumps(
                    [
                        "دامنهٔ حرکت را کنترل کنید و زانوها را هم‌راستا نگه دارید.",
                        "اگر درد تیز یا از دست‌رفتن کنترل ایجاد شد، حرکت را متوقف کنید.",
                    ],
                    ensure_ascii=False,
                ),
                "short_description_en": (
                    f"{correction['name_en']} identified from the attached owner video."
                ),
                "steps_en": json.dumps(_INSTRUCTIONS_EN[kind], ensure_ascii=False),
                "form_cues_en": json.dumps(
                    [
                        "Keep the trunk controlled.",
                        "Move through a pain-free range.",
                        "Use a steady tempo.",
                    ],
                    ensure_ascii=False,
                ),
                "common_mistakes_en": json.dumps(
                    [
                        "Letting the knees collapse inward.",
                        "Using momentum.",
                        "Losing foot pressure.",
                    ],
                    ensure_ascii=False,
                ),
                "breathing_en": "Inhale during the lowering phase and exhale while returning.",
                "source_metadata_en": _metadata_for_update(
                    row["source_metadata_en"], source_id, correction
                ),
            },
        )
        _update_associations(connection, row["id"], correction)


def downgrade() -> None:
    connection = op.get_bind()
    for source_id in CORRECTIONS:
        row = connection.execute(
            sa.text(
                "SELECT id FROM exercises "
                "WHERE source = 'owner-video' AND source_id = :source_id"
            ),
            {"source_id": source_id},
        ).mappings().first()
        if row is None:
            continue
        connection.execute(
            sa.text(
                "UPDATE exercises SET body_region = 'upper_body', primary_muscle = 'forearms', "
                "muscle_focus = 'general_forearms', difficulty = 'beginner', "
                "movement_pattern = 'other', exercise_type = 'other', "
                "needs_review = TRUE, is_programmable = FALSE "
                "WHERE id = :id"
            ),
            {"id": row["id"]},
        )
        _update_associations(
            connection,
            row["id"],
            {
                "equipment": (Equipment.OTHER,),
                "caution_tags": (ExerciseCautionTag.OTHER,),
            },
        )
