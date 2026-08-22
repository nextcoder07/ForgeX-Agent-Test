"""
Judge Calibration API Router.
"""

from __future__ import annotations

from fastapi import APIRouter
from app.models.failure import CalibrationReport
from app.core.evaluation.calibration_engine import run_judge_calibration_benchmark

router = APIRouter(prefix="/calibration", tags=["Calibration"])


@router.get("", response_model=CalibrationReport)
def get_calibration_benchmark():
    return run_judge_calibration_benchmark()
