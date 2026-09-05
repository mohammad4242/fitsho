def get_focus(title, muscles):
    t = title.lower()
    
    if "full body" in t: return "full_body"
    if "upper" in t: return "upper"
    if "lower" in t: return "lower"
    
    if t.startswith("push"):
        if "chest" in t: return "chest_triceps"
        if "shoulders" in t: return "shoulders_traps"
        return "push"
        
    if t.startswith("pull"):
        if "thickness" in t or "width" in t: return "back_biceps"
        return "pull"
        
    if "legs" in t:
        if "posterior" in t: return "posterior_chain_core"
        if "quadriceps" in t: return "quadriceps_calves"
        return "lower"
        
    if "squat" in t: return "quadriceps_calves"
    if "deadlift" in t or "hamstrings" in t: return "posterior_chain_core"
    if "quadriceps" in t: return "quadriceps_calves"
    
    if "bench" in t: return "chest_triceps"
    
    if t.startswith("chest"):
        if "triceps" in t or t == "chest" or "volume" in t or "heavy" in t: return "chest_triceps"
        if "back" in t or "shoulders" in t: return "upper"
        return "other"
        
    if t.startswith("back"):
        if "biceps" in t or t == "back" or "thickness" in t or "width" in t or "arms" in t: return "back_biceps"
        if "rear delts" in t or "shoulders" in t: return "upper"
        return "other"
        
    if "shoulders" in t or "overhead press" in t: return "shoulders_traps"
    if "press + pull" in t: return "upper"
    
    return "other"

import ast

with open("backend/app/training_templates/seed_data.py", "r") as f:
    code = f.read()

tree = ast.parse(code)

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_day':
        title = node.args[0].value
        
        # Extract muscles
        muscles_tuple = node.args[2]
        muscles = []
        if isinstance(muscles_tuple, ast.Tuple):
            for elt in muscles_tuple.elts:
                if isinstance(elt, ast.Attribute) and isinstance(elt.value, ast.Name):
                    muscles.append(elt.attr)
        focus = get_focus(title, muscles)
        print(f"{focus:20} | {title:25} | {muscles}")
