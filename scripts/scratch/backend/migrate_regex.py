import re
import sys

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


with open("app/training_templates/seed_data.py", "r") as f:
    content = f.read()

def repl(m):
    prefix = m.group(1)
    title_en = m.group(2)
    middle = m.group(3)
    title_fa = m.group(4)
    suffix = m.group(5)
    
    focus = get_focus(title_en)
    
    return f'{prefix}"{title_en}"{middle}"{title_fa}",\n                "{focus}"{suffix}'

# Match _day( optionally followed by newlines and spaces, then "title_en", optionally followed by newlines/spaces, then "title_fa",
# then followed by , or )
pattern = re.compile(r'(_day\(\s*)"([^"]+)"(,\s*)"([^"]+)"(,\s*)')
new_content = pattern.sub(repl, content)

with open("app/training_templates/seed_data.py", "w") as f:
    f.write(new_content)
