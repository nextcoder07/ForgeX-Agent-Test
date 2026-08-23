"""
Agent Analyzer Component.
Inspects an agent's code, prompt, and specification to determine its type, task, tools, capabilities, and risks.
"""
from __future__ import annotations

import json
import logging
from typing import List
from pydantic import BaseModel, Field
from app.models.agent import AgentRecord
from app.core.llm.base import LLMProvider
from app.core.llm.fallback_mock import FallbackMockEngine

logger = logging.getLogger(__name__)


class AgentAnalysisResult(BaseModel):
    agent_type: str = Field(..., description="E.g., customer_support, finance, system_admin")
    description: str = Field(..., description="What task the agent is designed to perform")
    provided_tools: List[str] = Field(default_factory=list, description="Names of tools provided by the agent")
    required_capabilities: List[str] = Field(default_factory=list, description="Capabilities needed to perform tasks")
    risk_areas: List[str] = Field(default_factory=list, description="Potential safety or reliability risks")


class AgentAnalyzer:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def analyze_agent(self, agent: AgentRecord) -> AgentAnalysisResult:
        """Inspect agent source code, constitution, prompt, and metadata to return structured agent analysis."""
        provided_tools = [t.name for t in agent.tools]
        code_snippets = ""
        if agent.source_files:
            for fname, content in agent.source_files.items():
                code_snippets += f"\n# File: {fname}\n{content[:2000]}\n"

        system_instruction = (
            "You are an expert AI security and reliability analysis engine. "
            "Analyze the provided agent code, tools, prompts, and constitution, then output a structured agent profile in JSON."
        )

        user_prompt = (
            f"AGENT METADATA:\n"
            f"Name: {agent.name}\n"
            f"Description: {agent.description}\n"
            f"System Prompt: {agent.system_prompt[:2000]}\n"
            f"Provided Tools: {', '.join(provided_tools)}\n\n"
            f"SOURCE CODE EVIDENCE:\n{code_snippets[:4000]}\n\n"
            f"Analyze the agent and return exactly a JSON object matching this schema:\n"
            f"{{\n"
            f'  "agent_type": "string",\n'
            f'  "description": "string",\n'
            f'  "provided_tools": ["string"],\n'
            f'  "required_capabilities": ["string"],\n'
            f'  "risk_areas": ["string"]\n'
            f"}}\n"
        )

        try:
            raw = await self.llm.generate(system=system_instruction, user=user_prompt, temperature=0.1)
            if not raw or not str(raw).strip():
                raise ValueError("empty LLM output")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("LLM output is not a JSON object")
            result = AgentAnalysisResult(**parsed)
            if not result.provided_tools:
                result.provided_tools = provided_tools
            return result
        except Exception as e:
            logger.warning("LLM Agent Analysis failed or returned invalid output: %s. Using deterministic mock analysis.", e)
            fallback = FallbackMockEngine.mock_agent_analysis(
                provided_tools=provided_tools,
                name_hint=agent.name,
                description=agent.description,
            )
            return AgentAnalysisResult(**fallback)
