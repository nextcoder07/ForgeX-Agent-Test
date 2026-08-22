"""
MockLLM Provider for Mode 3 (Simulation).
Enables deterministic testing, tool-call testing, failure testing, regression testing,
malformed response testing, timeout testing, and controlled behavior testing.
Supports test case defined `mock_behavior`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from app.core.llm.base import LLMProvider
from app.core.llm.fallback_mock import FallbackMockEngine

logger = logging.getLogger(__name__)


class MockLLM(LLMProvider):
    def __init__(self, mock_behavior: Optional[Dict[str, Any]] = None):
        self.mock_behavior = mock_behavior or {}
        self.model_name = "mock-llm-simulator"

    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Generates mock output according to mock_behavior if present, or deterministic fallback."""
        if self.mock_behavior:
            b_type = self.mock_behavior.get("response", "text")
            
            if b_type == "tool_call":
                tool_name = self.mock_behavior.get("tool", "refund")
                arguments = self.mock_behavior.get("arguments", {})
                return json.dumps({
                    "action": "tool_call",
                    "tool": tool_name,
                    "arguments": arguments,
                    "mock_status": self.mock_behavior.get("status", "simulated")
                })
            
            elif b_type == "malformed":
                return "MALFORMED_JSON_RESPONSE{{{incomplete_syntax"
            
            elif b_type == "timeout":
                raise TimeoutError("MockLLM simulated network/API timeout error")
            
            elif b_type == "error":
                err_msg = self.mock_behavior.get("error_message", "500 Internal Server Error from Model Gateway")
                return json.dumps({"error": err_msg, "code": 500})
            
            elif b_type == "text":
                return self.mock_behavior.get("text", "MockLLM deterministic simulated response.")

        # Default fallback deterministic output
        return json.dumps(FallbackMockEngine.mock_agent_understanding(user))

    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        return FallbackMockEngine.mock_agent_understanding(code_evidence)

    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_critic_decision(scenario_json)

    async def generate_scenarios(self, agent_spec: Dict[str, Any], strategy_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        return FallbackMockEngine.mock_scenario_generation(agent_spec, strategy_plan)

    async def judge_trace(self, trace_json: Dict[str, Any], constraints: List[str]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_judge_verdict(trace_json, constraints)
