from app.workouts.program_engine.engine import generate_program
import ast
import inspect
src = inspect.getsource(generate_program)
tree = ast.parse(src)
print(ast.dump(tree, indent=2))
