from app.workouts.program_engine.engine import generate_program
import inspect
src = inspect.getsource(generate_program)
print(src[src.find("errors = ("):src.find("return ProgramGenerationResult")])
