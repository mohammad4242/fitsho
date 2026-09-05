import ast

with open("app/workouts/program_engine/engine.py", "r") as f:
    tree = ast.parse(f.read())
    
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == "_day_count_errors":
        print(ast.unparse(node))
