import os
import re
import json

snapshot_files = [
    "backend/app/services/__snapshot_agents.json",
    "backend/app/services/__snapshot_agent_behavior_profiles.json",
    "backend/app/services/__snapshot_agent_dependencies.json",
    "backend/app/services/__snapshot_ai_generation_runs.json",
    "backend/app/services/__snapshot_dependency_bindings.json",
    "backend/app/services/__snapshot_evaluation_runs.json",
    "backend/app/services/__snapshot_execution_sessions.json",
    "backend/app/services/__snapshot_pipeline_runs.json",
    "backend/app/services/__snapshot_sandbox_specifications.json",
    "backend/app/services/__snapshot_scenarios.json"
]

def merge_file(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "<<<<<<<" not in content:
        return

    # Extract HEAD block and remote block
    # Regex pattern matching standard git conflict markers in JSON files
    pattern = re.compile(r"<<<<<<< HEAD\s*(.*?)\s*=======\s*(.*?)\s*>>>>>>> [a-f0-9]+", re.DOTALL)
    
    def parse_part(raw_text):
        raw_text = raw_text.strip()
        if not raw_text:
            return {}
        if not raw_text.startswith("{"):
            raw_text = "{" + raw_text
        if not raw_text.endswith("}"):
            raw_text = raw_text + "}"
        try:
            return json.loads(raw_text)
        except Exception:
            # Fallback line-by-line parsing
            res = {}
            for line in raw_text.splitlines():
                line = line.strip().rstrip(",")
                if ":" in line:
                    try:
                        k, v = line.split(":", 1)
                        k_obj = json.loads(k.strip())
                        v_obj = json.loads(v.strip())
                        res[k_obj] = v_obj
                    except Exception:
                        pass
            return res

    matches = pattern.findall(content)
    merged = {}
    
    # Try parsing the whole file if structure permits or process parts
    for head_part, remote_part in matches:
        h_dict = parse_part(head_part)
        r_dict = parse_part(remote_part)
        merged.update(h_dict)
        merged.update(r_dict)

    # Write back clean merged JSON dictionary
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"Reconciled snapshot file: {filepath} with {len(merged)} entries.")

if __name__ == "__main__":
    for sf in snapshot_files:
        merge_file(sf)
