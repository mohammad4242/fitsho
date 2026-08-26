from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseContentType,
    ExerciseLabel,
    ExerciseType,
    MediaPresentation,
    MediaRole,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.schemas import ExerciseDetail
from app.exercises.taxonomy import is_compatible_muscle_focus
from app.profile.enums import ExperienceLevel, FitnessGoal
from app.training_templates.catalog_invariants import validate_catalog_topology
from app.training_templates.models import (
    StructureFamily,
    StructureSplitType,
    TrainingTemplateMethod,
    TrainingTemplateSlotPriority,
)
from app.training_templates.tags import TemplateFocusTag, validate_template_focus_tags
from app.workouts.program_engine.enums import (
    BodyPosition,
    ImpactLimit,
    Laterality,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
)

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
TextItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
OptionalMetadata = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=500),
]
ProgrammingMetadataTag = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
SubstitutionGroup = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=120),
]
SourceUrl = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=8, max_length=500),
]


class AdminExerciseFilters(BaseModel):
    content_type: ExerciseContentType | None = None
    body_region: BodyRegion | None = None
    primary_muscle: MuscleGroup | None = None
    muscle_focus: MuscleFocus | None = None
    equipment: Equipment | None = None
    difficulty: Difficulty | None = None
    exercise_type: ExerciseType | None = None
    labels: list[ExerciseLabel] | None = None
    search: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] = None
    is_active: bool | None = None
    is_programmable: bool | None = None
    needs_review: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_muscle_focus(self) -> "AdminExerciseFilters":
        if self.muscle_focus is not None and not is_compatible_muscle_focus(
            self.primary_muscle,
            self.muscle_focus,
        ):
            raise ValueError("Muscle focus requires a compatible primary muscle")
        return self


class AdminExerciseMediaAssetInput(BaseModel):
    id: UUID | None = None
    presentation: MediaPresentation
    role: MediaRole
    sort_order: int = Field(default=0, ge=0)
    upload_index: int | None = Field(default=None, ge=0)
    media_source_url: OptionalMetadata = None
    media_license: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=120),
    ] = None
    media_attribution: OptionalMetadata = None


class AdminExerciseMediaAssetDetail(BaseModel):
    id: UUID
    presentation: MediaPresentation
    role: MediaRole
    sort_order: int
    media_path: str
    media_type: MediaType
    media_source_url: str | None
    media_license: str | None
    media_attribution: str | None


class AdminExerciseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Slug
    name_en: Name
    name_fa: Name
    content_type: ExerciseContentType = ExerciseContentType.EXERCISE
    body_region: BodyRegion | None
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    secondary_muscles: list[MuscleGroup] = Field(default_factory=list)
    equipment: list[Equipment] = Field(min_length=1)
    difficulty: Difficulty
    instructions_en: list[TextItem] = Field(min_length=3, max_length=6)
    instructions_fa: list[TextItem] = Field(min_length=3, max_length=6)
    safety_notes_en: list[TextItem] = Field(default_factory=list)
    movement_pattern: MovementPattern = MovementPattern.OTHER
    exercise_type: ExerciseType = ExerciseType.OTHER
    caution_tags: list[ExerciseCautionTag] = Field(default_factory=list)
    is_programmable: bool = False
    body_position: BodyPosition | None = None
    stability_demand: StabilityDemand | None = None
    skill_demand: SkillDemand | None = None
    impact_level: ImpactLimit | None = None
    axial_loading_level: LoadLimit | None = None
    fatigue_cost: int | None = Field(default=None, ge=1, le=5)
    setup_cost: int | None = Field(default=None, ge=1, le=5)
    laterality: Laterality | None = None
    substitution_group: SubstitutionGroup = None
    range_of_motion_profile: list[ProgrammingMetadataTag] | None = None
    safety_notes_fa: list[TextItem] = Field(default_factory=list)
    is_active: bool = True
    needs_review: bool = False
    labels: list[ExerciseLabel] = Field(default_factory=list)
    media_source_url: OptionalMetadata = None
    media_license: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=120),
    ] = None
    media_attribution: OptionalMetadata = None
    media_assets: list[AdminExerciseMediaAssetInput] = Field(default_factory=list)


class AdminExerciseDetail(ExerciseDetail):
    media_assets: list[AdminExerciseMediaAssetDetail] = Field(default_factory=list)  # type: ignore[assignment]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    caution_tags: list[ExerciseCautionTag]
    is_programmable: bool
    body_position: BodyPosition | None = None
    stability_demand: StabilityDemand | None = None
    skill_demand: SkillDemand | None = None
    impact_level: ImpactLimit | None = None
    axial_loading_level: LoadLimit | None = None
    fatigue_cost: int | None = None
    setup_cost: int | None = None
    laterality: Laterality | None = None
    substitution_group: str | None = None
    range_of_motion_profile: list[str] | None = None


class PaginatedAdminExercises(BaseModel):
    items: list[AdminExerciseDetail]
    page: int
    page_size: int
    total: int
    total_pages: int


class AdminTrainingTemplateExercise(BaseModel):
    id: UUID
    slug: str
    name_en: str
    name_fa: str
    needs_review: bool


class AdminTrainingTemplateSlot(BaseModel):
    id: UUID
    slot_order: int
    exercise_slug_hint: str
    placeholder_name_en: str | None
    placeholder_name_fa: str | None
    target_muscles: list[MuscleGroup]
    movement_pattern: MovementPattern
    intensity_method: TrainingTemplateMethod
    adaptation_priority: TrainingTemplateSlotPriority
    superset_group: str | None
    superset_exercise_id: UUID | None
    sets: int
    rep_min: int
    rep_max: int
    target_rir: int
    rest_seconds: int
    exercise: AdminTrainingTemplateExercise | None
    superset_exercise: AdminTrainingTemplateExercise | None = None


class AdminTrainingTemplateDay(BaseModel):
    id: UUID
    day_number: int
    title_en: str
    title_fa: str
    structure_focus: str
    direct_target_muscles: list[MuscleGroup]
    slots: list[AdminTrainingTemplateSlot]


class AdminTrainingTemplateProgrammingRationale(BaseModel):
    title_en: str
    title_fa: str
    detail_en: str
    detail_fa: str


class AdminTrainingProgramStructureDay(BaseModel):
    id: UUID
    day_number: int
    label_en: str
    label_fa: str
    day_type: str | None


class AdminTrainingProgramStructure(BaseModel):
    id: UUID
    slug: str
    name_en: str
    name_fa: str
    days_per_week: int
    family: StructureFamily | None
    split_type: StructureSplitType | None
    description_en: str | None
    description_fa: str | None
    is_active: bool
    structure_days: list[AdminTrainingProgramStructureDay]


class AdminTrainingProgramStructuresResponse(BaseModel):
    items: list[AdminTrainingProgramStructure]


class AdminTrainingProgramTemplate(BaseModel):
    id: UUID
    slug: str
    name_en: str
    name_fa: str
    description_en: str
    description_fa: str
    days_per_week: int
    supported_levels: list[ExperienceLevel]
    focus_tags: list[TemplateFocusTag]
    intensity_methods: list[TrainingTemplateMethod]
    programming_rationale: list[AdminTrainingTemplateProgrammingRationale]
    source_name: str
    source_url: str
    days: list[AdminTrainingTemplateDay]
    # Nullable: admin-created programs without a structure assignment return null
    structure_id: UUID | None = None


class AdminTrainingProgramTemplatesResponse(BaseModel):
    items: list[AdminTrainingProgramTemplate]


class AdminTrainingTemplateRationaleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_en: Name
    title_fa: Name
    detail_en: TextItem
    detail_fa: TextItem


class AdminTrainingProgramStructureDayWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int = Field(ge=1, le=6)
    label_en: Name
    label_fa: Name
    day_type: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=60),
    ] = None


class AdminTrainingProgramStructureWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    name_en: Name
    name_fa: Name
    days_per_week: int = Field(ge=2, le=6)
    family: StructureFamily | None = None
    split_type: StructureSplitType | None = None
    description_en: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = None
    description_fa: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    ] = None
    days: list[AdminTrainingProgramStructureDayWrite] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_classification(self) -> "AdminTrainingProgramStructureWrite":
        if self.days_per_week <= 3:
            if self.family is not None or self.split_type is not None:
                raise ValueError("2- and 3-day structures cannot have a family or split type")
            return self
        if self.family is None:
            raise ValueError("4- to 6-day structures require a family")
        if self.family is StructureFamily.UPPER_LOWER and self.split_type is not None:
            raise ValueError("Upper / Lower structures cannot have a split type")
        if self.family is StructureFamily.SPLIT and self.split_type is None:
            raise ValueError("Split structures require a split type")
        return self


class AdminTrainingTemplateSlotWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: UUID
    display_name_en: Name | None = None
    display_name_fa: Name | None = None
    target_muscles: list[MuscleGroup] = Field(min_length=1)
    movement_pattern: MovementPattern
    intensity_method: TrainingTemplateMethod = TrainingTemplateMethod.STANDARD
    adaptation_priority: TrainingTemplateSlotPriority = TrainingTemplateSlotPriority.ACCESSORY
    superset_group: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
    ] = None
    superset_exercise_id: UUID | None = None
    sets: int = Field(ge=1, le=10)
    rep_min: int = Field(ge=1, le=100)
    rep_max: int = Field(ge=1, le=100)
    target_rir: int = Field(ge=0, le=6)
    rest_seconds: int = Field(ge=0, le=600)

    @model_validator(mode="after")
    def validate_rep_range(self) -> "AdminTrainingTemplateSlotWrite":
        if self.rep_min > self.rep_max:
            raise ValueError("Minimum repetitions cannot exceed maximum repetitions")
        return self

    @model_validator(mode="after")
    def validate_superset(self) -> "AdminTrainingTemplateSlotWrite":
        if self.intensity_method is TrainingTemplateMethod.SUPERSET:
            if self.superset_exercise_id is None:
                raise ValueError("Superset slots require a superset_exercise_id")
            if self.exercise_id == self.superset_exercise_id:
                raise ValueError("Superset exercises must be different")
        elif self.superset_exercise_id is not None:
            raise ValueError("Only superset slots may declare a superset_exercise_id")
        return self


class AdminTrainingTemplateDayWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_en: Name
    title_fa: Name
    structure_focus: Name
    direct_target_muscles: list[MuscleGroup] = Field(min_length=1)
    slots: list[AdminTrainingTemplateSlotWrite] = Field(min_length=1)


class AdminTrainingProgramTemplateWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_en: Name
    name_fa: Name
    description_en: TextItem
    description_fa: TextItem
    days_per_week: int = Field(ge=2, le=6)
    supported_levels: list[ExperienceLevel] = Field(min_length=1, max_length=4)
    focus_tags: list[TemplateFocusTag] = Field(min_length=1, max_length=12)
    intensity_methods: list[TrainingTemplateMethod] = Field(min_length=1, max_length=3)
    programming_rationale: list[AdminTrainingTemplateRationaleWrite] = Field(
        min_length=5,
        max_length=5,
    )
    source_name: Name
    source_url: SourceUrl
    days: list[AdminTrainingTemplateDayWrite]
    # Optional: link this program to an existing TrainingProgramStructure.
    # structure.days_per_week must equal days_per_week if provided.
    structure_id: UUID | None = None

    @field_validator("supported_levels")
    @classmethod
    def validate_supported_levels_are_unique(
        cls,
        supported_levels: list[ExperienceLevel],
    ) -> list[ExperienceLevel]:
        if len(supported_levels) != len(set(supported_levels)):
            raise ValueError("Supported levels must be unique")
        return supported_levels

    @model_validator(mode="after")
    def validate_program_shape(self) -> "AdminTrainingProgramTemplateWrite":
        if len(self.days) != self.days_per_week:
            raise ValueError("Program must contain one configured day per training day")
        if len(self.intensity_methods) != len(set(self.intensity_methods)):
            raise ValueError("Intensity methods must be unique")
        if len(self.focus_tags) != len(set(self.focus_tags)):
            raise ValueError("Focus tags must be unique")
        validate_template_focus_tags(
            self.focus_tags,
            intensity_methods=self.intensity_methods,
            days=self.days,
        )
        validate_catalog_topology(self.days_per_week, self.focus_tags)
        slot_methods = {
            slot.intensity_method for day in self.days for slot in day.slots
        }
        if set(self.intensity_methods) != slot_methods:
            raise ValueError("Template intensity methods must match configured slot methods")
        novice_levels = {ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER}
        if novice_levels.intersection(self.supported_levels) and slot_methods - {
            TrainingTemplateMethod.STANDARD
        }:
            raise ValueError("First Month and Beginner templates cannot use advanced methods")
        for day in self.days:
            print("METHODS:", [slot.intensity_method for slot in day.slots])
            exercise_count = sum(2 if slot.intensity_method == TrainingTemplateMethod.SUPERSET else 1 for slot in day.slots)
            if exercise_count < 4 or exercise_count > 9:
                raise ValueError("Each day must contain exactly 4 to 9 runtime exercises (a superset counts as two)")
        for day in self.days:
            for slot in day.slots:
                if slot.intensity_method is TrainingTemplateMethod.SUPERSET:
                    if slot.superset_exercise_id is None:
                        raise ValueError("Superset slots require a superset_exercise_id")
                    if slot.exercise_id == slot.superset_exercise_id:
                        raise ValueError("Superset exercises must be different")
                else:
                    if slot.superset_exercise_id is not None:
                        raise ValueError("Only superset slots may declare a superset_exercise_id")
        return self
