import libcst as cst
import ast

def get_focus(title):
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

class DayModifier(cst.CSTTransformer):
    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.CSTNode:
        if isinstance(original_node.func, cst.Name) and original_node.func.value == '_day':
            if len(original_node.args) >= 2:
                title_arg = original_node.args[0].value
                if isinstance(title_arg, cst.SimpleString):
                    title_en = title_arg.evaluated_value
                    focus = get_focus(title_en)
                    
                    # Create the new argument
                    new_arg = cst.Arg(value=cst.SimpleString(f'"{focus}"'))
                    
                    # If the args are multiline (have trailing commas or just newlines),
                    # we should probably just inject the new arg at index 2.
                    # libcst preserves whitespace, so we just insert it.
                    
                    new_args = list(updated_node.args)
                    # Copy whitespace from the second argument to the new argument to preserve formatting
                    second_arg = new_args[1]
                    new_arg = new_arg.with_changes(comma=second_arg.comma)
                    
                    new_args.insert(2, new_arg)
                    return updated_node.with_changes(args=new_args)
        return updated_node

with open("backend/app/training_templates/seed_data.py", "r") as f:
    code = f.read()

tree = cst.parse_module(code)
modified_tree = tree.visit(DayModifier())

with open("backend/app/training_templates/seed_data.py", "w") as f:
    f.write(modified_tree.code)
