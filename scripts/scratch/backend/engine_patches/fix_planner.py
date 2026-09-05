import re
from pathlib import Path

path = Path("volume_planner.py")
content = path.read_text()

content = content.replace(
    "from app.workouts.program_engine.volume_policy import (",
    "from app.workouts.program_engine.volume_policy import (\n    session_direct_volume_range,\n    weekly_direct_volume_range,",
)

old_loop = """        is_secondary = muscle in SECONDARY_MUSCLES
        muscle_minimum = secondary_minimum if is_secondary else minimum
        muscle_maximum = secondary_maximum if is_secondary else maximum"""

new_loop = """        is_secondary = muscle in SECONDARY_MUSCLES
        range_limit = weekly_direct_volume_range(muscle, request.source.training_age_months)
        if range_limit:
            muscle_minimum = range_limit.minimum
            muscle_maximum = range_limit.maximum
        else:
            muscle_minimum = secondary_minimum if is_secondary else minimum
            muscle_maximum = secondary_maximum if is_secondary else maximum"""

content = content.replace(old_loop, new_loop)

old_target_loop = """        hard_maximum = (
            muscle_maximum + 4
            if muscle in explicit_priorities
            else muscle_maximum + 2
        )
        if is_secondary:
            hard_maximum = muscle_maximum + 4"""

new_target_loop = """        if range_limit:
            hard_maximum = muscle_maximum
        else:
            hard_maximum = (
                muscle_maximum + 4
                if muscle in explicit_priorities
                else muscle_maximum + 2
            )
            if is_secondary:
                hard_maximum = muscle_maximum + 4"""

content = content.replace(old_target_loop, new_target_loop)

old_split = """            split_maximum = min(
                hard_maximum,
                ruleset.max_sets_per_muscle_per_session * frequency,
            )"""

new_split = """            sess_range = session_direct_volume_range(muscle, request.source.training_age_months)
            sess_max = sess_range.maximum if sess_range else ruleset.max_sets_per_muscle_per_session
            split_maximum = min(
                hard_maximum,
                sess_max * frequency,
            )"""

content = content.replace(old_split, new_split)

path.write_text(content)
print("Fixed volume_planner")
