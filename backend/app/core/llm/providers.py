"""
Pluggable LLM Provider Implementations: OpenAI, Anthropic, Ollama, and Generic Provider Factory.
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, List, Optional
from app.core.llm.base import LLMProvider
from app.core.llm.gemini_provider import GeminiProvider
from app.core.llm.mock_llm import MockLLM
from app.core.llm.fallback_mock import FallbackMockEngine

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = "", model_name: str = "gpt-5"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model_name

    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY unavailable for Faithful OpenAI execution mode")
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            res = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=temperature
            )
            return res.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"OpenAI generation error: {e}")
            raise e

    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        return FallbackMockEngine.mock_agent_understanding(code_evidence)

    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_critic_decision(scenario_json)

    async def generate_scenarios(self, agent_spec: Dict[str, Any], strategy_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        return FallbackMockEngine.mock_scenario_generation(agent_spec, strategy_plan)

    async def judge_trace(self, trace_json: Dict[str, Any], constraints: List[str]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_judge_verdict(trace_json, constraints)


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str = "", model_name: str = "claude-3-5-sonnet"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model_name = model_name

    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY unavailable for Faithful Anthropic execution mode")
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            res = client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}]
            )
            return res.content[0].text if res.content else ""
        except Exception as e:
            logger.warning(f"Anthropic generation error: {e}")
            raise e

    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        return FallbackMockEngine.mock_agent_understanding(code_evidence)

    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_critic_decision(scenario_json)

    async def generate_scenarios(self, agent_spec: Dict[str, Any], strategy_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        return FallbackMockEngine.mock_scenario_generation(agent_spec, strategy_plan)

    async def judge_trace(self, trace_json: Dict[str, Any], constraints: List[str]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_judge_verdict(trace_json, constraints)


class OllamaProvider(LLMProvider):
    """Local model provider (Ollama) — NO API Key required."""
    def __init__(self, endpoint: str = "http://localhost:11434", model_name: str = "llama3"):
        self.endpoint = endpoint
        self.model_name = model_name

    async def generate(self, system: str, user: str, temperature: float = 0.2) -> str:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                res = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={"model": self.model_name, "system": system, "prompt": user, "stream": False},
                    timeout=30.0
                )
                if res.status_code == 200:
                    return res.json().get("response", "")
                raise RuntimeError(f"Ollama server returned HTTP {res.status_code}")
        except Exception as e:
            logger.warning(f"Ollama local model generation error: {e}")
            return json.dumps(FallbackMockEngine.mock_agent_understanding(user))

    async def analyze(self, code_evidence: str, doc_evidence: str) -> Dict[str, Any]:
        return FallbackMockEngine.mock_agent_understanding(code_evidence)

    async def critique(self, scenario_json: Dict[str, Any], agent_spec: Dict[str, Any]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_critic_decision(scenario_json)

    async def generate_scenarios(self, agent_spec: Dict[str, Any], strategy_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        return FallbackMockEngine.mock_scenario_generation(agent_spec, strategy_plan)

    async def judge_trace(self, trace_json: Dict[str, Any], constraints: List[str]) -> Dict[str, Any]:
        return FallbackMockEngine.mock_judge_verdict(trace_json, constraints)


from app.core.llm.llm_config import LLMConfig

def get_provider(provider_name: str, model_name: str = "", api_key: str = "", mock_behavior: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """Factory function returning appropriate LLMProvider instance."""
    p_lower = (provider_name or "").lower()
    if p_lower == "openai":
        return OpenAIProvider(api_key=api_key, model_name=model_name or "gpt-5")
    elif p_lower in ["google", "gemini"]:
        return GeminiProvider(api_key=api_key, model_name=model_name or LLMConfig.GEMINI_MODEL)
    elif p_lower == "anthropic":
        return AnthropicProvider(api_key=api_key, model_name=model_name or "claude-3-5-sonnet")
    elif p_lower in ["ollama", "local"]:
        return OllamaProvider(model_name=model_name or "llama3")
    elif p_lower == "mock":
        return MockLLM(mock_behavior=mock_behavior)
    
    # Default to GeminiProvider
    return GeminiProvider(api_key=api_key, model_name=model_name or LLMConfig.GEMINI_MODEL)
