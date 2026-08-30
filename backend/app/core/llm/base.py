"""
Pluggable LLM Provider Abstract Base Class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMProvider(ABC):
    def __init__(self):
        self.is_available: bool = True
        self.last_error_reason: Optional[str] = None

    @abstractmethod
    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Generic structured text / JSON generation."""
        pass

    @abstractmethod
    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        """Perform semantic agent understanding and normalized spec extraction."""
        pass

    async def analyze_evidence_packet(self, evidence_packet: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a complete structured evidence packet using the master analyzer instruction."""
        return await self.analyze(str(evidence_packet.get("source_files", "")), str(evidence_packet.get("deterministic_evidence", "")))

    @abstractmethod
    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """2nd-pass scenario critic verifying relevance, executability, and safety."""
        pass

    @abstractmethod
    async def generate_scenarios(self, agent_spec: Dict[str, Any], strategy_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate targeted multi-turn test scenarios covering strategy categories."""
        pass

    @abstractmethod
    async def judge_trace(self, trace_json: Dict[str, Any], constraints: list[str]) -> Dict[str, Any]:
        """Semantic LLM Judge evaluating execution traces against safety policies."""
        pass

