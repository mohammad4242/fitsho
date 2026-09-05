import ast
import os

for root, _, files in os.walk('app'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            try:
                tree = ast.parse(open(path).read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        if 'DAY_COUNT_MISMATCH' in node.value:
                            print(f"FOUND IN CONSTANT: {path}:{node.lineno}")
                    elif isinstance(node, ast.Str):
                        if 'DAY_COUNT_MISMATCH' in node.s:
                            print(f"FOUND IN STR: {path}:{node.lineno}")
            except SyntaxError:
                pass
