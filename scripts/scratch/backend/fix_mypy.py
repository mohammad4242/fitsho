with open("tests/workouts/program_engine/test_phase11_benchmark.py", "r") as f:
    content = f.read()

content = content.replace("from tests.workouts.program_engine.phase11_benchmark import (", "from typing import cast\nfrom app.workouts.program_engine.schemas import ProgramGenerationResult\nfrom tests.workouts.program_engine.phase11_benchmark import (")

content = content.replace("_category(result, template_fallback, issues)", "_category(cast(ProgramGenerationResult, result), template_fallback, issues)")
content = content.replace("_construction_path(result, template_fallback)", "_construction_path(cast(ProgramGenerationResult, result), template_fallback)")
content = content.replace("_category(result, template_success, issues)", "_category(cast(ProgramGenerationResult, result), template_success, issues)")

with open("tests/workouts/program_engine/test_phase11_benchmark.py", "w") as f:
    f.write(content)
