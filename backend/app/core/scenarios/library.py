"""
Scenario Library serialization manager for Member 1.
Serializes generated scenarios to JSON and loads them.
"""
from __future__ import annotations

import json
import os
from typing import List
from app.models.agent_test_spec import ScenarioDefinition

class ScenarioLibrary:
    @staticmethod
    def save_scenarios(scenarios: List[ScenarioDefinition], filepath: str) -> None:
        """Serializes list of ScenarioDefinition objects to a JSON file."""
        # Ensure directories exist
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        # Serialize Pydantic objects
        serialized = [sc.model_dump() if hasattr(sc, "model_dump") else sc.dict() for sc in scenarios]
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_scenarios(filepath: str) -> List[ScenarioDefinition]:
        """Loads and deserializes ScenarioDefinition objects from a JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Scenario library file '{filepath}' does not exist.")
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        scenarios = []
        if isinstance(data, list):
            for item in data:
                scenarios.append(ScenarioDefinition(**item))
        return scenarios
