"""
Gemini Key & Session Management Observability Router.
"""

from __future__ import annotations

from typing import List, Dict, Any
from fastapi import APIRouter
from app.core.llm.key_manager import UnifiedKeyManager

router = APIRouter(prefix="/gemini", tags=["Gemini"])

@router.get("/keys", response_model=List[Dict[str, Any]])
def list_keys():
    """Returns safe key registration and operational health status."""
    return UnifiedKeyManager().get_all_keys_status()
