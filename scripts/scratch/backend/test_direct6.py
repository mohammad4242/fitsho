from app.workouts.program_engine.engine import generate_program
import inspect
src = inspect.getsource(generate_program)
print("\n".join(line for line in src.split("\n") if "errors =" in line or "error_code=" in line))
