from app.workouts.program_engine.engine import _training_day_error
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from audit_phase11_benchmark import benchmark_profiles, profile_to_request

for p in benchmark_profiles():
    req = profile_to_request(p, enforce_matrix=False)
    if req.available_training_days == 5 and req.training_experience.value == "novice":
        print("ERROR:", _training_day_error(req, RULESET))
        print("requested_days:", req.available_training_days)
        print("experience_level:", req.training_experience.value)
        break
