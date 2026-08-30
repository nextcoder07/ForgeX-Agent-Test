"""
Central API Router Aggregator.
"""

from __future__ import annotations

from fastapi import APIRouter
from app.api.auth import router as auth_router
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
from app.api.datasets import router as datasets_router
from app.api.dependencies import router as dependencies_router
from app.api.gemini import router as gemini_router
from app.api.execution import router as execution_router
from app.api.llm_health import router as llm_health_router
from app.api.repair import router as repair_router
from app.api.diagnosis import router as diagnosis_router
from app.api.model_connections import router as model_connections_router
from app.api.training import router as training_router
from app.api.pipeline_status import router as pipeline_status_router
from app.agent_testers.router import router as agent_testers_router
from app.core.meta_eval.router import router as platform_ai_router
from app.api.admin_telemetry import router as admin_telemetry_router
from app.api.improve import router as improve_router
from app.api.agent_config import router as agent_config_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(agents_router)
api_router.include_router(agent_config_router)
api_router.include_router(intake_router)
api_router.include_router(capabilities_router)
api_router.include_router(scenarios_router)
api_router.include_router(evaluations_router)
api_router.include_router(live_attack_router)
api_router.include_router(calibration_router)
api_router.include_router(pipeline_router)
api_router.include_router(activity_router)
api_router.include_router(executions_router)
api_router.include_router(datasets_router)
api_router.include_router(dependencies_router)
api_router.include_router(gemini_router)
api_router.include_router(execution_router)
api_router.include_router(llm_health_router)
api_router.include_router(repair_router)
api_router.include_router(diagnosis_router)
api_router.include_router(model_connections_router)
api_router.include_router(training_router)
api_router.include_router(pipeline_status_router)
api_router.include_router(agent_testers_router)
api_router.include_router(platform_ai_router)
api_router.include_router(admin_telemetry_router)
api_router.include_router(improve_router)


@api_router.get("/health")
async def health_check():
    return {"status": "ok", "service": "ForgeX Platform API"}




