"""
Agent Registry API Router.
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
    all_agents = store.list_agents()
    # Filter by user_id or return sample agents if user has not created any yet
    user_agents = [a for a in all_agents if getattr(a, 'user_id', None) == current_user.user_id]
    if not user_agents:
        # Include default sample agents for initial exploration
        user_agents = [a for a in all_agents if getattr(a, 'user_id', None) in ("default_user", "system", None)]
    return user_agents


@router.get("/{agent_id}", response_model=AgentRecord)
def get_agent(agent_id: str, current_user: UserRecord = Depends(get_current_user)):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.post("", response_model=AgentRecord)
def create_agent(agent: AgentRecord, current_user: UserRecord = Depends(get_current_user)):
    agent.user_id = current_user.user_id
    store.save_agent(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: str, current_user: UserRecord = Depends(get_current_user)):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    store.delete_agent(agent_id)
    return {"status": "success", "message": f"Agent '{agent_id}' and all associated scenarios, results, and files deleted successfully"}
