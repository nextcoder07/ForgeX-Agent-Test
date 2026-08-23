"""
Tool Analyzer Component.
Identifies required tools for the agent's tasks, checks availability, and flags missing tools.
"""
from __future__ import annotations

import json
import logging
from typing import List
from pydantic import BaseModel, Field
from app.models.agent import AgentRecord
from app.core.llm.base import LLMProvider
from app.core.llm.fallback_mock import FallbackMockEngine
from app.core.analysis.tool_catalog import tool_is_provided

logger = logging.getLogger(__name__)


class ToolAnalysisItem(BaseModel):
    name: str
    purpose: str
    capabilities: List[str] = Field(default_factory=list)
    risk_level: str  # "low", "medium", "high", "critical"
    available: bool
    mock_required: bool


class ToolAnalysisResult(BaseModel):
    required_tools: List[ToolAnalysisItem] = Field(default_factory=list)


class ToolAnalyzer:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def analyze_tools(self, agent: AgentRecord) -> ToolAnalysisResult:
        """Determines required tools and checks availability against agent's provided tools."""
        provided_names = [t.name for t in agent.tools]

        system_instruction = (
            "You are an expert systems integration and dependency mapping engine. "
            "Identify all tools needed by the agent to perform its stated goals. "
            "Output your findings matching the requested JSON schema."
        )

        user_prompt = (
            f"AGENT PROFILE:\n"
            f"Name: {agent.name}\n"
            f"Description: {agent.description}\n"
            f"System Prompt: {agent.system_prompt[:2000]}\n"
            f"Provided Tools: {', '.join(provided_names)}\n\n"
            f"List the required tools. For each tool, specify its name, purpose, capabilities, and estimated risk_level.\n"
            f"Set 'available' to true if the tool name is in the Provided Tools list, otherwise false.\n"
            f"Set 'mock_required' to true if 'available' is false, otherwise false.\n\n"
            f"Return exactly a JSON object matching this schema:\n"
            f"{{\n"
            f'  "required_tools": [\n'
            f"    {{\n"
            f'      "name": "string",\n'
            f'      "purpose": "string",\n'
            f'      "capabilities": ["string"],\n'
            f'      "risk_level": "low" | "medium" | "high" | "critical",\n'
            f'      "available": true | false,\n'
            f'      "mock_required": true | false\n'
            f"    }}\n"
            f"  ]\n"
            f"}}\n"
        )

        required_tools: List[ToolAnalysisItem] = []
        try:
            raw = await self.llm.generate(system=system_instruction, user=user_prompt, temperature=0.1)
            if not raw or not str(raw).strip():
                raise ValueError("empty LLM output")
            parsed = json.loads(raw)
            items = parsed.get("required_tools", []) if isinstance(parsed, dict) else []
            if not items:
                raise ValueError("no required_tools in LLM output")
            for item in items:
                required_tools.append(ToolAnalysisItem(**item))
        except Exception as e:
            logger.warning("LLM Tool Analysis failed: %s. Falling back to mock tool analysis.", e)
            fallback = FallbackMockEngine.mock_tool_analysis(
                provided_tools=provided_names,
                text_hint=f"{agent.description}\n{agent.system_prompt}",
            )
            required_tools = [ToolAnalysisItem(**item) for item in fallback.get("required_tools", [])]

        for item in required_tools:
            available = tool_is_provided(item.name, provided_names)
            item.available = available
            item.mock_required = not available

        return ToolAnalysisResult(required_tools=required_tools)
