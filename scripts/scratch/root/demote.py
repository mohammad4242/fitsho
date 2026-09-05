import re

with open("backend/app/workouts/program_engine/validation.py", "r") as f:
    content = f.read()

hard_errors = [
    "SESSION_DURATION_UNDER_TARGET",
    "SESSION_DURATION_TARGET_UNSATISFIED",
    "SESSION_DURATION_EXCEEDED",
    "SESSION_DURATION_OVER_TARGET",
    "INACTIVE_EXERCISE_SELECTED",
    "NONPROGRAMMABLE_EXERCISE_SELECTED",
    "REVIEW_PENDING_EXERCISE_SELECTED",
    "BLOCKED_EXERCISE_SELECTED",
    "BLOCKED_MOVEMENT_PATTERN_SELECTED",
    "BLOCKED_CAUTION_TAG_SELECTED",
    "UNAVAILABLE_EQUIPMENT_SELECTED",
    "INVALID_EXERCISE_PRESCRIPTION",
    "TRAINING_DAY_COUNT_MISMATCH",
    "REQUESTED_TRAINING_DAYS_UNSATISFIED",
    "SAFETY_STATUS_DISALLOWS_GENERATION",
]

def replace_error(match):
    err_msg = match.group(2)
    # Check if err_msg starts with any of the hard_errors or is formatted
    is_hard = False
    for he in hard_errors:
        if he in err_msg:
            is_hard = True
            break
    if "TRAINING_DAY_COUNT_MISMATCH" in err_msg or "REQUESTED_TRAINING_DAYS_UNSATISFIED" in err_msg:
        is_hard = True
        
    if is_hard:
        return match.group(0)
    else:
        return match.group(1) + "warnings.append(" + match.group(2) + ")"

new_content = re.sub(r'(\s+)errors\.append\((.+)\)', replace_error, content)

with open("backend/app/workouts/program_engine/validation.py", "w") as f:
    f.write(new_content)
