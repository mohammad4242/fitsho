import re
from pathlib import Path

# 1. volume_policy.py
policy_code = """
from typing import NamedTuple

LARGE_MUSCLES = frozenset({
    MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS,
    MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES
})

SMALL_MUSCLES = frozenset({
    MuscleGroup.BICEPS, MuscleGroup.TRICEPS, MuscleGroup.FOREARMS, MuscleGroup.CALVES
})

class VolumeRange(NamedTuple):
    minimum: int
    maximum: int

def volume_experience_band(training_age_months: int) -> str:
    if training_age_months <= 5:
        return "NOVICE"
    if training_age_months <= 24:
        return "INTERMEDIATE"
    return "ADVANCED"

def weekly_direct_volume_range(muscle: MuscleGroup, training_age_months: int) -> VolumeRange | None:
    band = volume_experience_band(training_age_months)
    if muscle in LARGE_MUSCLES:
        if band == "NOVICE": return VolumeRange(6, 12)
        if band == "INTERMEDIATE": return VolumeRange(8, 16)
        return VolumeRange(10, 20)
    if muscle in SMALL_MUSCLES:
        if band == "NOVICE": return VolumeRange(4, 8)
        if band == "INTERMEDIATE": return VolumeRange(6, 12)
        return VolumeRange(8, 16)
    return None

def session_direct_volume_range(muscle: MuscleGroup, training_age_months: int) -> VolumeRange | None:
    band = volume_experience_band(training_age_months)
    if muscle in LARGE_MUSCLES:
        if band == "NOVICE": return VolumeRange(3, 6)
        if band == "INTERMEDIATE": return VolumeRange(4, 8)
        return VolumeRange(5, 10)
    if muscle in SMALL_MUSCLES:
        if band == "NOVICE": return VolumeRange(2, 4)
        if band == "INTERMEDIATE": return VolumeRange(3, 6)
        return VolumeRange(4, 8)
    return None
"""
vp = Path("volume_policy.py")
content = vp.read_text()
if "LARGE_MUSCLES =" not in content:
    vp.write_text(content + "\n" + policy_code)

print("Fixed volume_policy.py")
