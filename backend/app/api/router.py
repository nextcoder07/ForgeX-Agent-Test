"""
Central API Router Aggregator.
"""

from __future__ import annotations

from fastapi import APIRouter
from app.api.agents import router as agents_router
from app.api.intake import router as intake_router
from app.api.capabilities import router as capabilities_router
from app.api.scenarios import router as scenarios_router
from app.api.evaluations import router as evaluations_router
from app.api.live_attack import router as live_attack_router
from app.api.calibration import router as calibration_router
from app.api.pipeline import router as pipeline_router
from app.api.activity import router as activity_router
from app.api.executions import router as executions_router
from app.api.dependencies import router as dependencies_router
from app.api.gemini import router as gemini_router
from app.api.execution import router as execution_router

api_router = APIRouter(prefix="/api")
api_router.include_router(agents_router)
api_router.include_router(intake_router)
api_router.include_router(capabilities_router)
api_router.include_router(scenarios_router)
api_router.include_router(evaluations_router)
api_router.include_router(live_attack_router)
api_router.include_router(calibration_router)
api_router.include_router(pipeline_router)
api_router.include_router(activity_router)
api_router.include_router(executions_router)
api_router.include_router(dependencies_router)
api_router.include_router(gemini_router)
api_router.include_router(execution_router)
