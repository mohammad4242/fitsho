from app.workouts.program_engine.schemas import DerivedConstraints, ProgramGenerationRequest


def derive_constraints(request: ProgramGenerationRequest) -> DerivedConstraints:
    patterns = set(request.blocked_movement_patterns)
    caution_tags = set(request.blocked_caution_tags)
    allowed_rom = set(request.allowed_range_of_motion)
    impact_limit = request.impact_limit
    axial_load_limit = request.axial_load_limit
    overhead_limit = request.overhead_limit
    balance_requirement = request.balance_requirement

    for limitation in request.injuries_and_limitations:
        patterns.update(limitation.blocked_movement_patterns)
        caution_tags.update(limitation.blocked_caution_tags)
        allowed_rom.update(limitation.allowed_range_of_motion)
        if limitation.impact_limit is not None:
            impact_limit = min(impact_limit, limitation.impact_limit, key=_limit_rank)
        if limitation.axial_load_limit is not None:
            axial_load_limit = min(axial_load_limit, limitation.axial_load_limit, key=_limit_rank)
        if limitation.overhead_limit is not None:
            overhead_limit = min(overhead_limit, limitation.overhead_limit, key=_limit_rank)
        if limitation.balance_requirement is not None:
            balance_requirement = limitation.balance_requirement

    return DerivedConstraints(
        available_equipment=request.available_equipment,
        blocked_exercises=request.blocked_exercises,
        blocked_movement_patterns=frozenset(patterns),
        blocked_caution_tags=frozenset(caution_tags),
        allowed_range_of_motion=frozenset(allowed_rom),
        impact_limit=impact_limit,
        axial_load_limit=axial_load_limit,
        overhead_limit=overhead_limit,
        balance_requirement=balance_requirement,
    )


def _limit_rank(value: object) -> int:
    return {"none": 0, "low": 1, "moderate": 2, "high": 3}[str(value)]
