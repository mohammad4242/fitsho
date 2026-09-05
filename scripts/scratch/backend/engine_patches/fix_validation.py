import re
from pathlib import Path

path = Path("validation.py")
content = path.read_text()

old_session = """        configured_limit = program.aggregate_metrics.get(
            "reference_max_sets_per_muscle_per_session",
            ruleset.max_sets_per_muscle_per_session,
        )
        per_session_limit = (
            configured_limit
            if isinstance(configured_limit, int)
            else ruleset.max_sets_per_muscle_per_session
        )
        if any(value > per_session_limit for value in per_session.values()):
            errors.append("PER_SESSION_MUSCLE_VOLUME_EXCEEDED")"""

new_session = """        from app.workouts.program_engine.volume_policy import session_direct_volume_range
        from app.exercises.enums import MuscleGroup
        for muscle_str, value in per_session.items():
            muscle_enum = next((m for m in MuscleGroup if m.value == muscle_str), None)
            if muscle_enum is not None:
                sess_range = session_direct_volume_range(muscle_enum, request.source.training_age_months)
                dynamic_user_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session
            else:
                dynamic_user_max = ruleset.max_sets_per_muscle_per_session
            
            configured_limit = program.aggregate_metrics.get("reference_max_sets_per_muscle_per_session")
            if isinstance(configured_limit, int):
                per_session_limit = min(dynamic_user_max, configured_limit)
            else:
                per_session_limit = dynamic_user_max
                
            if value > per_session_limit:
                errors.append("PER_SESSION_MUSCLE_VOLUME_EXCEEDED")"""

content = content.replace(old_session, new_session)

old_weekly = """    for muscle, value in effective.items():
        if value > ruleset.maximum_sets[request.training_status]:
            errors.append("EFFECTIVE_MUSCLE_VOLUME_EXCEEDED")
            break"""

new_weekly = """    from app.workouts.program_engine.volume_policy import weekly_direct_volume_range
    for muscle_str, value in effective.items():
        muscle_enum = next((m for m in MuscleGroup if m.value == muscle_str), None)
        range_limit = weekly_direct_volume_range(muscle_enum, request.source.training_age_months) if muscle_enum else None
        
        if range_limit:
            direct_val = direct.get(muscle_str, 0)
            if direct_val > range_limit.maximum:
                errors.append("EFFECTIVE_MUSCLE_VOLUME_EXCEEDED")
                break
        else:
            if value > ruleset.maximum_sets[request.training_status]:
                errors.append("EFFECTIVE_MUSCLE_VOLUME_EXCEEDED")
                break"""

content = content.replace(old_weekly, new_weekly)

path.write_text(content)
print("Fixed validation")
