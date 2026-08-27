"""
ML Dataset Export API Router.
Exposes REST endpoints to export structured agent testing datasets for downstream ML training.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Response, HTTPException
from app.core.dataset_exporter import (
    extract_ml_dataset_records,
    export_dataset_jsonl,
    export_dataset_csv,
    export_dataset_sharegpt,
    export_dataset_alpaca
)

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("/summary")
def get_dataset_summary(agent_id: Optional[str] = None):
    """Returns summary statistics for accumulated ML failure prediction training data."""
    records = extract_ml_dataset_records(agent_id=agent_id)
    passed_count = sum(1 for r in records if r["target_labels"]["passed"])
    failed_count = len(records) - passed_count
    
    categories = {}
    for r in records:
        cat = r["target_labels"]["primary_finding_category"]
        if cat != "NONE":
            categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_dataset_records": len(records),
        "passed_records": passed_count,
        "failed_records": failed_count,
        "failure_categories": categories,
        "features_available": [
            "agent_features.domain",
            "agent_features.tool_count",
            "scenario_features.category",
            "execution_features.total_events",
            "execution_features.total_latency_ms",
            "target_labels.passed",
            "target_labels.primary_finding_category"
        ]
    }


@router.get("/export")
def export_dataset(agent_id: Optional[str] = None, format: str = "jsonl"):
    """Exports structured ML training dataset file in JSONL, CSV, ShareGPT, or Alpaca format."""
    records = extract_ml_dataset_records(agent_id=agent_id)
    fmt = format.lower()

    if fmt == "csv":
        csv_content = export_dataset_csv(records)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="agent_reliability_dataset.csv"'}
        )
    elif fmt == "sharegpt":
        sharegpt_content = export_dataset_sharegpt(records)
        return Response(
            content=sharegpt_content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="agent_sharegpt_dataset.json"'}
        )
    elif fmt == "alpaca":
        alpaca_content = export_dataset_alpaca(records)
        return Response(
            content=alpaca_content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="agent_alpaca_dataset.json"'}
        )

    jsonl_content = export_dataset_jsonl(records)
    return Response(
        content=jsonl_content,
        media_type="application/jsonlines",
        headers={"Content-Disposition": 'attachment; filename="agent_reliability_dataset.jsonl"'}
    )
