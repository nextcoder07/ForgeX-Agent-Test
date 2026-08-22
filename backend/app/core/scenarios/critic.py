"""
Scenario Critic for Member 1.
Evaluates proposed test scenarios for relevance, executability, and triviality.
Supports deterministic checks and a pluggable LLM provider critic.
"""
from __future__ import annotations

import logging
import asyncio
from typing import List, Optional, Dict, Any

from app.models.agent_test_spec import AgentTestSpecification, ScenarioDefinition
from app.core.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)

async def critique_scenarios(
    scenarios: List[ScenarioDefinition],
    spec: AgentTestSpecification,
    api_key: Optional[str] = None
) -> List[ScenarioDefinition]:
    """
    Main entrypoint: critiques each scenario.
    Updates the critic_status, critic_feedback, and critic_confidence of each scenario.
    """
    critiqued = []
    llm = GeminiProvider(api_key=api_key) if (api_key or os.getenv("GEMINI_API_KEY")) else None

    # Check duplicates dynamically
    seen_messages = set()

    for sc in scenarios:
        # 1. Deterministic/Heuristic Critic Check
        status, reason, confidence = _run_heuristic_critic(sc, spec, seen_messages)
        
        sc.critic_status = status
        sc.critic_feedback = reason
        sc.critic_confidence = confidence
        
        # 2. Run pluggable LLM Critic if available and heuristic hasn't rejected it
        if llm and status != "REJECT":
            try:
                agent_dict = {
                    "name": spec.name,
                    "purpose": spec.purpose,
                    "instructions": spec.instructions_summary,
                    "capabilities": [c.capability_id for c in spec.capabilities]
                }
                sc_dict = {
                    "capability_id": sc.capability_id,
                    "category": sc.category,
                    "description": sc.description,
                    "input": sc.input,
                    "expected_behavior": sc.expected_behavior,
                    "required_tools": sc.required_tools
                }
                
                # Critique call
                critic_res = await llm.critique(sc_dict, agent_dict)
                passed = critic_res.get("passed", True)
                notes = critic_res.get("notes", "LLM validation passed.")
                relevance = float(critic_res.get("relevance_score", 1.0))
                
                if not passed:
                    sc.critic_status = "MODIFY"
                    sc.critic_feedback = f"LLM Critic suggests modification: {notes}"
                    sc.critic_confidence = min(sc.critic_confidence, relevance)
                else:
                    # Keep passed or upgrade
                    if sc.critic_status == "PASS":
                        sc.critic_feedback = f"Validated by Critic. {notes}"
                        
            except Exception as e:
                logger.warning(f"LLM Critic critique call failed: {e}. Retaining heuristic score.")

        critiqued.append(sc)
        
        # Mark user message as seen for duplication check
        msg = sc.input.get("message", "") if isinstance(sc.input, dict) else ""
        if msg:
            seen_messages.add(msg.strip().lower())
            
    return critiqued


def _run_heuristic_critic(
    sc: ScenarioDefinition,
    spec: AgentTestSpecification,
    seen_messages: set
) -> tuple[str, str, float]:
    """Helper running deterministic rule checks on individual scenarios."""
    # Check 1: Relevance to capability
    capabilities_ids = {c.capability_id.upper() for c in spec.capabilities}
    if sc.capability_id.upper() not in capabilities_ids and sc.capability_id != "GENERIC":
        return "REJECT", f"Capability ID '{sc.capability_id}' does not match any agent capabilities.", 1.0

    # Check 2: Meaningful/Empty details
    if not sc.description or len(sc.description.strip()) < 10:
        return "MODIFY", "Scenario description is too brief or empty.", 0.8

    # Check 3: Clear Expected Behavior
    if not sc.expected_behavior or len(sc.expected_behavior.strip()) < 10:
        return "MODIFY", "Expected behavior statement is too short or lacks clarity.", 0.8

    # Check 4: Executability (required tools match available tools)
    available_tools = {t.name.lower() for t in spec.tools}
    for tool in sc.required_tools:
        if tool.lower() not in available_tools:
            return "MODIFY", f"Required tool '{tool}' is not declared in agent tools.", 0.9

    # Check 5: Duplicate prompt check
    msg = sc.input.get("message", "") if isinstance(sc.input, dict) else ""
    if msg and msg.strip().lower() in seen_messages:
        return "REJECT", "Duplicate scenario input prompt detected.", 0.95

    # Check 6: Triviality check
    if msg and len(msg.strip()) < 6:
        return "REJECT", f"User input message '{msg}' is too short/trivial.", 0.9

    return "PASS", "Scenario meets quality checks.", 1.0
import os
