"""
Agent Registry API Router.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException
from app.models.agent import AgentRecord
from app.services.store import store

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=List[AgentRecord])
def list_agents():
    return store.list_agents()


@router.get("/{agent_id}", response_model=AgentRecord)
def get_agent(agent_id: str):
    agent = store.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent


@router.post("", response_model=AgentRecord)
def create_agent(agent: AgentRecord):
    store.save_agent(agent)
    return agent
