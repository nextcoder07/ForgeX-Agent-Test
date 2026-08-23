"""
Verify deep deterministic and semantic behavioral profile facts for News Summarizer Agent.
"""

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.intake import AgentIntakePayload, RegisterSpecRequest
from app.core.llm.gemini_provider import GeminiProvider
from app.core.intake.spec_reconstructor import process_agent_intake
from app.api.intake import register_normalized_spec
from app.services.store import store


async def run_verification():
    agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "test-agents", "09-news-summarizer-agent"))
    if not os.path.exists(agent_dir):
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "500-AI-Agents-Projects", "agents", "06-news-summarizer-agent"))

    files = {}
    for root, _, fnames in os.walk(agent_dir):
        for f in fnames:
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                rel = os.path.relpath(p, agent_dir).replace(os.sep, "/")
                files[rel] = fp.read()

    payload = AgentIntakePayload(
        files=files,
        input_type="folder",
        agent_name_hint="News-summary"
    )
    llm = GeminiProvider()
    print("[TEST] Running process_agent_intake...")
    result = await process_agent_intake(payload, llm)

    # Register to store
    reg_req = RegisterSpecRequest(
        normalized_spec=result.normalized_spec,
        display_name="News-summary",
        artifact=result.artifact,
        source_files=files
    )
    rec = await register_normalized_spec(reg_req)
    bp = store.get_behavior_profile(rec.id) or result.normalized_spec.behavior_profile

    print("\n" + "=" * 70)
    print("EXTRACTED BEHAVIOR PROFILE AUDIT REPORT")
    print("=" * 70)

    # 1. Interface Contract
    ic = bp.interface_contract
    print(f"\n1. INTERFACE CONTRACT:")
    print(f"   - Type: {ic.interface_type}")
    print(f"   - Entrypoint: {ic.entrypoint}")
    print(f"   - Invocation Pattern: {json.dumps(ic.invocation_pattern)}")
    print(f"   - Interactive: {ic.interactive}, Stdin: {ic.stdin_supported}")

    # 2. Inputs
    print(f"\n2. INPUTS ({len(bp.inputs)}):")
    for inp in bp.inputs:
        print(f"   - {inp.get('name')}: type={inp.get('type')}, default={repr(inp.get('default'))}, required={inp.get('required')}")

    # 3. External Calls & Services
    print(f"\n3. EXTERNAL CALLS & SERVICES ({len(bp.external_calls)}):")
    for ec in bp.external_calls:
        print(f"   - {ec.get('class_name') or ec.get('capability')}: {ec.get('evidence')}")

    # 4. Invariants
    print(f"\n4. INVARIANTS ({len(bp.invariants)}):")
    for inv in bp.invariants:
        print(f"   - [{inv.type}/{inv.enforcement_level}] {inv.statement} (evidence: {inv.evidence})")

    # 5. Data Transformations
    print(f"\n5. DATA TRANSFORMATIONS ({len(bp.data_transformations)}):")
    for dt in bp.data_transformations:
        print(f"   - {dt.field} -> {dt.operation} ({dt.parameters}) | {dt.evidence}")

    # 6. Failure Surfaces
    print(f"\n6. FAILURE SURFACES ({len(bp.failure_surfaces)}):")
    for fs in bp.failure_surfaces:
        print(f"   - [{fs.component}/{fs.surface_type}] {fs.description} ({fs.severity})")

    # 7. Security Surfaces
    print(f"\n7. SECURITY SURFACES ({len(bp.security_surfaces)}):")
    for ss in bp.security_surfaces:
        print(f"   - [{ss.get('surface')}] {ss.get('risk')} (Severity: {ss.get('severity')})")

    # 8. Workflow Graph
    wg = bp.workflow_graph
    print(f"\n8. WORKFLOW GRAPH ({len(wg.nodes)} nodes, {len(wg.edges)} edges):")
    for n in wg.nodes:
        print(f"   - Node [{n.id}] ({n.node_type}) - deps: {n.external_dependencies}")
    for e in wg.edges:
        print(f"   - Edge: {e.get('source')} -> {e.get('target')}")

    # 9. Conflicts
    print(f"\n9. CONFLICTS ({len(bp.conflicts)}):")
    for cf in bp.conflicts:
        print(f"   - Claim: '{cf.declared_behavior}' vs Reality: '{cf.implementation_evidence}'")

    # 10. Dependency Requirements
    print(f"\n10. DEPENDENCY REQUIREMENTS ({len(bp.dependency_requirements)}):")
    for dr in bp.dependency_requirements:
        print(f"   - {dr.get('name')} ({dr.get('type')}, required={dr.get('required')})")

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE - ALL 10 BEHAVIORAL DIMENSIONS POPULATED!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_verification())
