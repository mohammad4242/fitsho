import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.exercises.enums import MediaPresentation
from app.exercises.owner_video_media import PreparedOwnerVideo

SOURCE_ID = "a" * 64
EXERCISE_ID = UUID("11111111-1111-1111-1111-111111111111")


def valid_analysis_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_id": SOURCE_ID,
        "name_en": "Push-Up",
        "name_fa": "شنا سوئدی",
        "visible_text": ["PUSH UP"],
        "aliases_en": ["Press-Up"],
        "body_region": "upper_body",
        "primary_muscle": "chest",
        "muscle_focus": "mid_chest",
        "secondary_muscles": ["triceps"],
        "equipment": ["bodyweight"],
        "difficulty": "beginner",
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "labels": [],
        "caution_tags": ["wrist_loading"],
        "instructions_en": ["Set up.", "Lower with control.", "Press up."],
        "instructions_fa": ["آماده شو.", "کنترل‌شده پایین برو.", "بالا برو."],
        "safety_notes_en": ["Keep the neck neutral."],
        "safety_notes_fa": ["گردن را خنثی نگه دار."],
        "short_description_en": "A horizontal bodyweight press.",
        "short_description_fa": "یک حرکت فشاری افقی با وزن بدن.",
        "form_cues_en": ["Brace the trunk."],
        "form_cues_fa": ["میان‌تنه را ثابت نگه دار."],
        "common_mistakes_en": ["Letting the hips sag."],
        "common_mistakes_fa": ["افتادن لگن."],
        "breathing_en": "Exhale while pressing.",
        "breathing_fa": "هنگام بالا رفتن بازدم کن.",
        "presentation": "male",
        "presentation_confidence": 0.95,
        "identification_confidence": 0.98,
        "decision": "match_existing",
        "match_confidence": 0.97,
        "existing_exercise_id": str(EXERCISE_ID),
        "review_reasons": [],
    }
    payload.update(overrides)
    return payload


def catalogue_exercise() -> object:
    from app.exercises.owner_video_analysis import CatalogueExercise

    return CatalogueExercise(
        id=EXERCISE_ID,
        name_en="Push-Up",
        name_fa="شنا سوئدی",
        aliases_en=("Press-Up",),
        body_region="upper_body",
        primary_muscle="chest",
        movement_pattern="horizontal_push",
        equipment=("bodyweight",),
    )


def prepared_video(tmp_path: Path) -> PreparedOwnerVideo:
    work = tmp_path / SOURCE_ID
    work.mkdir(parents=True)
    muted = work / "muted.mp4"
    muted.write_bytes(b"muted")
    frames = tuple(work / f"frame-{index:02d}.jpg" for index in range(1, 6))
    for frame in frames:
        frame.write_bytes(b"\xff\xd8\xffframe")
    return PreparedOwnerVideo(
        source_path=tmp_path / "source.mp4",
        source_id=SOURCE_ID,
        muted_path=muted,
        frame_paths=frames,
        duration_seconds=1.0,
    )


def test_owner_video_analysis_rejects_invalid_structured_data() -> None:
    from app.exercises.owner_video_analysis import OwnerVideoAnalysis

    with pytest.raises(ValidationError):
        OwnerVideoAnalysis.model_validate(valid_analysis_payload(primary_muscle="unknown"))
    with pytest.raises(ValidationError):
        OwnerVideoAnalysis.model_validate(valid_analysis_payload(unexpected=True))
    with pytest.raises(ValidationError):
        OwnerVideoAnalysis.model_validate(
            valid_analysis_payload(instructions_en=["Set up.", "Press."])
        )
    with pytest.raises(ValidationError):
        OwnerVideoAnalysis.model_validate(valid_analysis_payload(source_id="ABC"))


def test_match_requires_catalogue_identity_name_taxonomy_and_equipment(
    test_settings: Settings,
) -> None:
    from app.exercises.owner_video_analysis import OwnerVideoAnalysis, resolve_existing_match

    catalogue = (catalogue_exercise(),)
    accepted = OwnerVideoAnalysis.model_validate(valid_analysis_payload())
    wrong_name = OwnerVideoAnalysis.model_validate(
        valid_analysis_payload(name_en="Floor Press", aliases_en=[], visible_text=[])
    )
    wrong_equipment = OwnerVideoAnalysis.model_validate(
        valid_analysis_payload(equipment=["dumbbell"])
    )
    uncertain = OwnerVideoAnalysis.model_validate(valid_analysis_payload(match_confidence=0.50))

    assert resolve_existing_match(accepted, catalogue, test_settings) == EXERCISE_ID
    assert resolve_existing_match(wrong_name, catalogue, test_settings) is None
    assert resolve_existing_match(wrong_equipment, catalogue, test_settings) is None
    assert resolve_existing_match(uncertain, catalogue, test_settings) is None


def test_exact_bilingual_name_match_reuses_existing_catalogue_card() -> None:
    from app.exercises.owner_video_analysis import OwnerVideoAnalysis, resolve_exact_name_match

    catalogue = (catalogue_exercise(),)
    same_name = OwnerVideoAnalysis.model_validate(
        valid_analysis_payload(decision="create_new", existing_exercise_id=None)
    )
    different_persian_name = OwnerVideoAnalysis.model_validate(
        valid_analysis_payload(
            decision="create_new",
            existing_exercise_id=None,
            name_fa="پرس سینه هالتر اسمیت",
        )
    )

    assert resolve_exact_name_match(same_name, catalogue) == EXERCISE_ID
    assert resolve_exact_name_match(different_persian_name, catalogue) is None


def test_presentation_uses_unspecified_below_confidence_threshold(
    test_settings: Settings,
) -> None:
    from app.exercises.owner_video_analysis import OwnerVideoAnalysis, resolve_presentation

    confident = OwnerVideoAnalysis.model_validate(valid_analysis_payload())
    uncertain = OwnerVideoAnalysis.model_validate(
        valid_analysis_payload(presentation="female", presentation_confidence=0.20)
    )

    assert resolve_presentation(confident, test_settings) is MediaPresentation.MALE
    assert resolve_presentation(uncertain, test_settings) is MediaPresentation.UNSPECIFIED


def test_codex_cli_receives_five_frames_schema_prompt_and_uses_cache(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.exercises.owner_video_analysis import CodexCliExerciseAnalyzer

    monkeypatch.chdir(tmp_path)
    prepared = prepared_video(Path("relative-work"))
    commands: list[list[str]] = []
    prompts: list[str] = []

    def runner(
        command: Sequence[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        commands.append(rendered)
        prompt = kwargs.get("input")
        assert isinstance(prompt, str)
        prompts.append(prompt)
        output_path = Path(rendered[rendered.index("--output-last-message") + 1])
        output_path.write_text(json.dumps(valid_analysis_payload()), encoding="utf-8")
        return subprocess.CompletedProcess(rendered, 0, "", "")

    analyzer = CodexCliExerciseAnalyzer(test_settings, runner=runner)
    first = analyzer.analyze(prepared, (catalogue_exercise(),))
    second = analyzer.analyze(prepared, (catalogue_exercise(),))

    assert first == second
    assert len(commands) == 1
    command = commands[0]
    assert command[:2] == [test_settings.owner_video_codex_path, "exec"]
    assert command.count("--image") == 5
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[-2:] == ["--", "-"]
    assert Path(command[command.index("-C") + 1]).is_absolute()
    assert Path(commands[0][commands[0].index("--image") + 1]).is_absolute()
    assert SOURCE_ID in prompts[0]
    assert "horizontal_push" in prompts[0]
    assert "Push-Up" in prompts[0]
    assert test_settings.database_url not in prompts[0]


def test_codex_analysis_rejects_digest_or_catalogue_id_not_in_request(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_analysis import (
        CodexCliExerciseAnalyzer,
        OwnerVideoAnalysisError,
    )

    prepared = prepared_video(tmp_path)

    def digest_runner(
        command: Sequence[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        output_path = Path(rendered[rendered.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(valid_analysis_payload(source_id="b" * 64)),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(rendered, 0, "", "")

    with pytest.raises(OwnerVideoAnalysisError, match="digest"):
        CodexCliExerciseAnalyzer(test_settings, runner=digest_runner).analyze(
            prepared,
            (catalogue_exercise(),),
        )

    other_id = "22222222-2222-2222-2222-222222222222"

    def id_runner(
        command: Sequence[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        output_path = Path(rendered[rendered.index("--output-last-message") + 1])
        output_path.write_text(
            json.dumps(valid_analysis_payload(existing_exercise_id=other_id)),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(rendered, 0, "", "")

    with pytest.raises(OwnerVideoAnalysisError, match="catalogue"):
        CodexCliExerciseAnalyzer(test_settings, runner=id_runner).analyze(
            prepared,
            (catalogue_exercise(),),
        )
