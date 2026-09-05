from app.workouts.program_engine.engine import generate_program
import inspect
src = inspect.getsource(generate_program)
lines = src.split('\n')
for i, line in enumerate(lines):
    if 'EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED' in line:
        for j in range(i-2, i+5):
            print(lines[j])
        break
