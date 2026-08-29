"""
Agent Registry API Router.
Scoped to active Workspace and Authenticated User.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.models.agent import AgentRecord
from app.services.store import store
from app.core.auth import get_current_user, UserRecord

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=List[AgentRecord])
def list_agents(current_user: UserRecord = Depends(get_current_user)):
    """List all agents belonging to the current active workspace / user."""
    all_agents = store.list_agents()
    if current_user.is_admin:
        return all_agents

    active_ws = current_user.active_workspace_id
    filtered = []
    for a in all_agents:
        a_ws = getattr(a, 'workspace_id', None)
        a_user = getattr(a, 'user_id', None)
        # Match by workspace, user, or unassigned default agent
        if (active_ws and a_ws == active_ws) or (a_user == current_user.user_id) or (not a_user and not a_ws):
            filtered.append(a)
    return filtered


@router.get("/{agent_id}", response_model=AgentRecord)
def get_agent(agent_id: str, current_user: UserRecord = Depends(get_current_user)):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.post("", response_model=AgentRecord)
def create_agent(agent: AgentRecord, current_user: UserRecord = Depends(get_current_user)):
    agent.user_id = current_user.user_id
    agent.owner_id = current_user.user_id
    agent.workspace_id = current_user.active_workspace_id
    store.save_agent(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, current_user: UserRecord = Depends(get_current_user)):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    store.delete_agent(agent_id)
    return {"status": "success", "message": f"Agent '{agent_id}' and all associated scenarios, results, and files deleted successfully"}
