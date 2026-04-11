
import json
import os
import re

def generate_nb():
    py_path = 'hotword_standalone.py'
    nb_path = 'hotword_standalone.ipynb'
    
    if not os.path.exists(py_path):
        print(f"Error: {py_path} not found.")
        return

    with open(py_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split the file by major section headers
    # We use regex to find the # =================... markers
    sections = re.split(r'# =+\n# \d+\..+\n# =+\n', content)
    
    # The first split is the header and imports
    header_and_imports = sections[0]
    # Find where imports actually start (after the file docstring)
    import_start_match = re.search(r'^import ', header_and_imports, re.MULTILINE)
    if import_start_match:
        imports_code = header_and_imports[import_start_match.start():]
    else:
        imports_code = header_and_imports

    # Subsequent sections
    # 1. Phoneme
    # 2. Algo
    # 3. RAG Fast
    # 4. Corrector
    # 5. Debug
    # 6. LLM
    # 7. Demo
    
    # For section 7, we need to split it further by "--- X. ... ---" markers
    demo_section = sections[7] if len(sections) > 7 else ""
    demo_subsections = re.split(r'# --- [A-F]\. .+ ---', demo_section)
    # demo_subsections[0] is usually empty or just whitespace
    
    # ID mapping
    id_map = {
        "a55132cd": imports_code.strip() + "\n",
        "37550be0": (sections[1] if len(sections) > 1 else "").strip() + "\n",
        "2c4b31e5": (sections[2] if len(sections) > 2 else "").strip() + "\n",
        "95cbd73d": (sections[3] if len(sections) > 3 else "").strip() + "\n",
        "470d32b3": (sections[4] if len(sections) > 4 else "").strip() + "\n",
        "86a83e87": (sections[5] if len(sections) > 5 else "").strip() + "\n",
        "a1988fe8": (sections[6] if len(sections) > 6 else "").strip() + "\n",
        "728a1784": (demo_subsections[1] if len(demo_subsections) > 1 else "").strip() + "\n", # A. Data
        "3ff9ad3b": (demo_subsections[2] if len(demo_subsections) > 2 else "").strip() + "\n", # B. Init
        "6e9c486b": (demo_subsections[3] if len(demo_subsections) > 3 else "").strip() + "\n", # C. Full Demo
        "6163670a": (demo_subsections[4] if len(demo_subsections) > 4 else "").strip() + "\n", # D. Debug Demo
        "033c045d": (demo_subsections[5] if len(demo_subsections) > 5 else "").strip() + "\n", # E. LLM Demo
        "77020cca": (demo_subsections[6] if len(demo_subsections) > 6 else "").strip() + "\n", # F. Perf
    }

    if not os.path.exists(nb_path):
        # Create a new basic notebook template if it doesn't exist
        nb = {
            "cells": [{"cell_type": "code", "execution_count": None, "id": cid, "metadata": {}, "outputs": [], "source": [src]} for cid, src in id_map.items()],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5
        }
    else:
        with open(nb_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        
        # Update existing cells
        for cell in nb['cells']:
            if 'id' in cell and cell['id'] in id_map:
                source = id_map[cell['id']]
                cell['source'] = [line + "\n" for line in source.splitlines()] if source.strip() else []
                # Remove trailing newline from last line for cleaner look in some editors, 
                # but Jupyter usually wants them. Let's keep it simple.
                if cell['source'] and cell['source'][-1].endswith("\n"):
                    cell['source'][-1] = cell['source'][-1].rstrip("\n")

    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print("Notebook generated successfully from hotword_standalone.py")

if __name__ == "__main__":
    generate_nb()
