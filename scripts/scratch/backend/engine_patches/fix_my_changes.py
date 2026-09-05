import re
from pathlib import Path

# session_duration.py
sd = Path("session_duration.py")
content = sd.read_text()
if "session_direct_volume_range" not in content:
    content = content.replace(
        "has_near_equivalent",
        "has_near_equivalent\nfrom app.workouts.program_engine.volume_policy import session_direct_volume_range",
    )
    content = content.replace(
        "if direct_sets + 1 > ruleset.max_sets_per_muscle_per_session:",
        "sess_range = session_direct_volume_range(exercise.primary_muscle, request.source.training_age_months)\n        sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n        if direct_sets + 1 > sess_max:",
    )
    content = content.replace(
        "sets = min(\n            ruleset.minimum_working_sets,\n            ruleset.max_sets_per_muscle_per_session,",
        "sess_range = session_direct_volume_range(candidate.primary_muscle, request.source.training_age_months)\n        sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n        sets = min(\n            ruleset.minimum_working_sets,\n            sess_max,",
    )
    content = content.replace(
        "if direct_sets_for_muscle + sets > ruleset.max_sets_per_muscle_per_session:",
        "if direct_sets_for_muscle + sets > sess_max:",
    )
    sd.write_text(content)
print("session_duration fixed")

# prescription.py
ps = Path("prescription.py")
content = ps.read_text()
if "sess_max" not in content:
    old_p = """            if primary_muscle in allocations:
                allocated_sets = next(allocations[primary_muscle])
                sets = max(ruleset.minimum_working_sets, allocated_sets)
                session_size_accessory = allocated_sets < ruleset.minimum_working_sets
            else:
                sets = min(
                    ruleset.max_sets_per_muscle_per_session,
                    ruleset.default_untracked_muscle_sets,
                )
            if primary_muscle is not None:
                remaining_direct_sets = (
                    ruleset.max_sets_per_muscle_per_session - direct_session_sets[primary_muscle]
                )"""
    new_p = """            if primary_muscle is not None:
                from app.workouts.program_engine.volume_policy import session_direct_volume_range
                sess_range = session_direct_volume_range(primary_muscle, request.source.training_age_months)
                sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session
            else:
                sess_max = ruleset.max_sets_per_muscle_per_session

            if primary_muscle in allocations:
                allocated_sets = next(allocations[primary_muscle])
                sets = max(ruleset.minimum_working_sets, allocated_sets)
                session_size_accessory = allocated_sets < ruleset.minimum_working_sets
            else:
                sets = min(
                    sess_max,
                    ruleset.default_untracked_muscle_sets,
                )
            if primary_muscle is not None:
                remaining_direct_sets = (
                    sess_max - direct_session_sets[primary_muscle]
                )"""
    content = content.replace(old_p, new_p)
    ps.write_text(content)
print("prescription fixed")

# priority_allocation.py
pa = Path("priority_allocation.py")
content = pa.read_text()
if "sess_max" not in content:
    content = content.replace(
        "def useful_frequency(self, target_sets: int, ruleset: ProgramRuleset) -> int:",
        "def useful_frequency(self, target_sets: int, ruleset: ProgramRuleset, muscle: MuscleGroup, request: NormalizedProgramRequest) -> int:",
    )
    content = content.replace(
        "required = max(1, math.ceil(target_sets / ruleset.max_sets_per_muscle_per_session))",
        "from app.workouts.program_engine.volume_policy import session_direct_volume_range\n        sess_range = session_direct_volume_range(muscle, request.source.training_age_months)\n        sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n        required = max(1, math.ceil(target_sets / sess_max))",
    )
    pa.write_text(content)
print("priority_allocation fixed")

# engine.py
eng = Path("engine.py")
content = eng.read_text()
if (
    "request: NormalizedProgramRequest"
    not in content.split("def _priority_metrics(")[1].split(")")[0]
):
    content = content.replace(
        "def _priority_metrics(\n    days: tuple[WorkoutDay, ...],\n    volume: WeeklyVolumePlan,\n    direct_sets: dict[str, int],\n    effective_sets: dict[str, float],\n    policy: PriorityAllocationPolicy,\n    ruleset: ProgramRuleset,\n) -> dict[str, dict[str, object]]:",
        "def _priority_metrics(\n    days: tuple[WorkoutDay, ...],\n    volume: WeeklyVolumePlan,\n    direct_sets: dict[str, int],\n    effective_sets: dict[str, float],\n    policy: PriorityAllocationPolicy,\n    ruleset: ProgramRuleset,\n    request: NormalizedProgramRequest,\n) -> dict[str, dict[str, object]]:",
    )
    content = content.replace(
        "useful_frequency = policy.useful_frequency(target, ruleset)",
        "useful_frequency = policy.useful_frequency(target, ruleset, muscle, request)",
    )
    content = content.replace(
        '"priority_metrics": _priority_metrics(\n            days,\n            volume,\n            effective_volume.direct_sets_by_muscle,\n            effective_volume.effective_sets_by_muscle,\n            priority_policy,\n            ruleset,\n        )',
        '"priority_metrics": _priority_metrics(\n            days,\n            volume,\n            effective_volume.direct_sets_by_muscle,\n            effective_volume.effective_sets_by_muscle,\n            priority_policy,\n            ruleset,\n            request,\n        )',
    )
    eng.write_text(content)
print("engine fixed")

# volume_repair.py
vr = Path("volume_repair.py")
content = vr.read_text()
if "session_direct_volume_range" not in content:
    content = content.replace(
        "    WorkoutDay,\n)",
        "    WorkoutDay,\n)\nfrom app.workouts.program_engine.volume_policy import session_direct_volume_range",
    )

    content = content.replace(
        "def _per_session_excessive(\n    days: list[list[ProgrammedExercise]], ruleset: ProgramRuleset\n) -> set[tuple[int, MuscleGroup]]:\n    excessive: set[tuple[int, MuscleGroup]] = set()\n    for day_index, exercises in enumerate(days):\n        direct = _direct_sets([exercises])\n        excessive.update(\n            (day_index, muscle)\n            for muscle, sets in direct.items()\n            if sets > ruleset.max_sets_per_muscle_per_session\n        )\n    return excessive",
        "def _per_session_excessive(\n    days: list[list[ProgrammedExercise]], request: NormalizedProgramRequest, ruleset: ProgramRuleset\n) -> set[tuple[int, MuscleGroup]]:\n    excessive: set[tuple[int, MuscleGroup]] = set()\n    for day_index, exercises in enumerate(days):\n        direct = _direct_sets([exercises])\n        for muscle, sets in direct.items():\n            sess_range = session_direct_volume_range(muscle, request.source.training_age_months)\n            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n            if sets > sess_max:\n                excessive.add((day_index, muscle))\n    return excessive",
    )
    content = content.replace(
        "per_session_excessive = _per_session_excessive(repaired, ruleset)",
        "per_session_excessive = _per_session_excessive(repaired, request, ruleset)",
    )

    content = content.replace(
        "recipient_muscle = recipient.primary_muscle\n            if (\n                recipient_muscle not in hard_direct_under\n                or direct_by_session[recipient_muscle] >= ruleset.max_sets_per_muscle_per_session\n                or recipient.sets >= _exercise_set_cap(recipient, days, request, targets, ruleset)\n            ):",
        "recipient_muscle = recipient.primary_muscle\n            sess_range = session_direct_volume_range(recipient_muscle, request.source.training_age_months)\n            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n            if (\n                recipient_muscle not in hard_direct_under\n                or direct_by_session[recipient_muscle] >= sess_max\n                or recipient.sets >= _exercise_set_cap(recipient, days, request, targets, ruleset)\n            ):",
    )

    content = content.replace(
        "sets = max(ruleset.minimum_working_sets, math.ceil(required_sets))\n            sets = min(sets, ruleset.max_sets_per_muscle_per_session)",
        "sets = max(ruleset.minimum_working_sets, math.ceil(required_sets))\n            sess_range = session_direct_volume_range(muscle, request.source.training_age_months)\n            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n            sets = min(sets, sess_max)",
    )

    content = content.replace(
        "session_overage = (\n                    direct_by_session[muscle] + sets - ruleset.max_sets_per_muscle_per_session\n                )",
        "session_overage = (\n                    direct_by_session[muscle] + sets - sess_max\n                )",
    )

    content = content.replace(
        "if direct_by_session[primary] >= ruleset.max_sets_per_muscle_per_session:\n                continue",
        "sess_range = session_direct_volume_range(primary, request.source.training_age_months)\n            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session\n            if direct_by_session[primary] >= sess_max:\n                continue",
    )

    content = content.replace(
        "return (\n        target.acceptable_maximum\n        if target is not None\n        else ruleset.maximum_sets[request.training_status]\n    )",
        "if target is not None:\n        return target.acceptable_maximum\n    if muscle_enum is not None:\n        from app.workouts.program_engine.volume_policy import weekly_direct_volume_range\n        range_limit = weekly_direct_volume_range(muscle_enum, request.source.training_age_months)\n        if range_limit: return range_limit.maximum\n    return ruleset.maximum_sets[request.training_status]",
    )

    content = content.replace(
        "return (\n        target.maximum_hard if target is not None else ruleset.maximum_sets[request.training_status]\n    )",
        "if target is not None:\n        return target.maximum_hard\n    if muscle_enum is not None:\n        from app.workouts.program_engine.volume_policy import weekly_direct_volume_range\n        range_limit = weekly_direct_volume_range(muscle_enum, request.source.training_age_months)\n        if range_limit: return range_limit.maximum\n    return ruleset.maximum_sets[request.training_status]",
    )

    content = content.replace(
        "preferred_frequency=priority_policy.useful_frequency(\n                                    targets[muscle].target_sets,\n                                    ruleset,\n                                ),",
        "preferred_frequency=priority_policy.useful_frequency(\n                                    targets[muscle].target_sets,\n                                    ruleset,\n                                    muscle,\n                                    request,\n                                ),",
    )

    content = content.replace(
        "preferred_frequency=priority_policy.useful_frequency(\n                                frequency_target.target_sets,\n                                ruleset,\n                            ),",
        "preferred_frequency=priority_policy.useful_frequency(\n                                frequency_target.target_sets,\n                                ruleset,\n                                primary,\n                                request,\n                            ),",
    )
    vr.write_text(content)
print("volume_repair fixed")

# weekly_distribution.py
wd = Path("weekly_distribution.py")
content = wd.read_text()
if "session_direct_volume_range" not in content:
    old_wd = """    if (
        tuple((day.day_index, day.weekday) for day in before)
        != tuple((day.day_index, day.weekday) for day in after)
        or _exercise_signatures(before) != _exercise_signatures(after)
        or _volume(before, ruleset) != _volume(after, ruleset)
        or any(
            sum(item.sets for item in day.exercises if item.primary_muscle is muscle)
            > ruleset.max_sets_per_muscle_per_session
            for day in after
            for muscle in {item.primary_muscle for item in day.exercises if item.primary_muscle}
        )
        or not recovery_spacing_is_valid(after, ruleset)"""
    new_wd = """    if (
        tuple((day.day_index, day.weekday) for day in before)
        != tuple((day.day_index, day.weekday) for day in after)
        or _exercise_signatures(before) != _exercise_signatures(after)
        or _volume(before, ruleset) != _volume(after, ruleset)
    ): return False
    
    from app.workouts.program_engine.volume_policy import session_direct_volume_range
    for day in after:
        for muscle in {item.primary_muscle for item in day.exercises if item.primary_muscle}:
            sess_range = session_direct_volume_range(muscle, request.source.training_age_months)
            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session
            if sum(item.sets for item in day.exercises if item.primary_muscle is muscle) > sess_max:
                return False

    if (
        not recovery_spacing_is_valid(after, ruleset)"""
    content = content.replace(old_wd, new_wd)
    wd.write_text(content)
print("weekly_distribution fixed")
