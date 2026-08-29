import asyncio
import os
import sys
import json
import uuid

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from app.api.intake import TEST_AGENTS_DIR, get_local_demo_agent_files, process_agent_intake, AgentIntakePayload
from app.models.agent import AgentRecord, ToolDefinition
from app.core.scenarios.scenario_generator import generate_scenarios_for_agent
from app.core.scenarios.strategy_planner import build_test_strategy
from app.core.scenarios.scenario_validator import hard_validate_scenarios
from app.core.scenarios.scenario_critic import critique_scenarios
from app.core.llm.providers import get_platform_provider

async def smoke_test():
    agent_dirs = [
        ("04-rag-agent", "Resume Evaluation Agent"),
    ]
    
    print("\n" + "="*80)
    print("STAGE 2 END-TO-END SCENARIO SMOKE TEST & GROUNDING AUDIT")
    print("="*80 + "\n")
    
    llm = get_platform_provider()
    
    for agent_dir, display_name in agent_dirs:
        dir_path = os.path.join(TEST_AGENTS_DIR, agent_dir)
        if not os.path.isdir(dir_path):
            continue
            
        data = get_local_demo_agent_files(agent_dir)
        name_hint = data["metadata"].get("name", display_name)
        payload = AgentIntakePayload(
            agent_name_hint=name_hint,
            domain=data["metadata"].get("domain", "general"),
            files=data["files"]
        )
        
        print(f"\n" + "="*80)
        print(f">>> Processing Agent Archetype: [{name_hint}] ({agent_dir})")
        print(f"="*80)
        
        # 1. Intake Stage 1
        understanding = await process_agent_intake(payload, llm)
        spec = understanding.normalized_spec
        
        # Convert to AgentRecord
        tools_list = []
        for t in spec.tools:
            tools_list.append(ToolDefinition(
                name=t.name,
                description=t.description or "",
                risk=getattr(t, "risk", getattr(t, "risk_level", "low"))
            ))
        
        agent = AgentRecord(
            id=f"agent-{uuid.uuid4().hex[:8]}",
            workspace_id="ws-demo",
            name=name_hint,
            description=spec.identity.get("description", f"Local agent {agent_dir}"),
            domain=spec.identity.get("domain", "general"),
            agent_spec=spec.model_dump(),
            tools=tools_list,
            source_files=data["files"]
        )
        
        print(f"✅ Stage 1 Intake Succeeded: ID={agent.id} | Tools={len(agent.tools)} | Domain={agent.domain}")
        
        # 2. Stage 2 Strategy Planning & Generation
        strategy = build_test_strategy(agent, desired_count=8)
        raw_scenarios = await generate_scenarios_for_agent(agent, strategy, llm)
        print(f"   Generated {len(raw_scenarios)} candidate scenarios from LLM.")
        
        # 3. Hard Deterministic Validator
        validated, report = hard_validate_scenarios(raw_scenarios, agent)
        print(f"   Hard Validator: {len(validated)}/{len(raw_scenarios)} passed ({len(report)} rejected).")
        
        # 4. LLM Critic
        critiqued = await critique_scenarios(validated, agent, llm)
        print(f"✅ Stage 2 Surviving Final Scenarios: {len(critiqued)}\n")
        
        # 5. Detailed Inspection of Surviving Scenarios
        for i, sc in enumerate(critiqued):
            category = sc.category.value if hasattr(sc.category, "value") else str(sc.category)
            subsystem = sc.target_subsystem.value if hasattr(sc.target_subsystem, "value") else str(sc.target_subsystem)
            print(f"  [{i+1}/{len(critiqued)}] [{category.upper()}] {sc.title}")
            print(f"    • Subsystem: {subsystem}")
            print(f"    • Risk Level: {sc.risk_level}")
            print(f"    • Required Capabilities: {sc.required_capabilities}")
            print(f"    • Required Services: {sc.required_services}")
            print(f"    • Target Workflow Node: {sc.target_workflow_node}")
            print(f"    • Invocation: {sc.invocation.get('command') or sc.invocation.get('args')}")
            print(f"    • Faults: {[{'tool': f.target_tool, 'type': f.fault_type} for f in sc.fault_injections]}")
            print(f"    • Assertions ({len(sc.assertions)}): {[a.assertion_type for a in sc.assertions]}")
            print(f"    • Quality Score: {sc.scenario_quality_score:.2f} | Critic: {sc.critic_passed}")
            print()

if __name__ == "__main__":
    asyncio.run(smoke_test())
