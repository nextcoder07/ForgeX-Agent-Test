from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.activity_log import activity_log, ActivityEvent

router = APIRouter(prefix="/activity", tags=["Activity"])

@router.get("/events", response_model=List[ActivityEvent])
def get_activity_events(
    limit: int = Query(50, ge=1, le=200),
    since: Optional[str] = Query(None)
):
    """Retrieve or poll behind-the-scenes activity log events."""
    return activity_log.get_events(limit=limit, since=since)
