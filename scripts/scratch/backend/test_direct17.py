from app.workouts.program_engine.engine import generate_program
print("generate_program is:", generate_program)
import inspect
print("is wrapped?", hasattr(generate_program, '__wrapped__'))
