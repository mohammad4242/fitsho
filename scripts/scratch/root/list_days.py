import ast

with open("backend/app/training_templates/seed_data.py", "r") as f:
    code = f.read()

tree = ast.parse(code)

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_day':
        title = node.args[0].value
        print(title)
