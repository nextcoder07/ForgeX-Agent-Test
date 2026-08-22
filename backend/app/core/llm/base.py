"""
Pluggable LLM Provider Abstract Base Class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Generic structured text / JSON generation."""
        pass

    @abstractmethod
    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        """Perform semantic agent understanding and normalized spec extraction."""
        pass

    @abstractmethod
    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        """2nd-pass scenario critic verifying relevance, executability, and safety."""
        pass

    @abstractmethod
    async def judge_trace(self, trace_json: Dict[str, Any], constraints: list[str]) -> Dict[str, Any]:
        """Semantic LLM Judge evaluating execution traces against safety policies."""
        pass
