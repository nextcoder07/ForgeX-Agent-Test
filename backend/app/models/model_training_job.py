"""
Model Training Job, Hardware Preflight, and Model Version Registry Models.
Manages the complete lifecycle for local/self-hosted model fine-tuning (QLoRA, SFT, DPO).
"""

from __future__ import annotations

import uuid
import datetime as dt
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


def _now() -> str:
    return dt.datetime.utcnow().isoformat() + "Z"


class HardwarePreflight(BaseModel):
    gpu_name: str = "NVIDIA GeForce RTX 3050 Laptop GPU"
    vram_mb: int = 4096
    cuda_available: bool = True
    cuda_version: str = "12.2"
    device_count: int = 1
    feasibility: str = "CAN_TRAIN_WITH_QLORA"  # "CAN_TRAIN", "CAN_TRAIN_WITH_QLORA", "MAY_TRAIN_WITH_OFFLOAD", "INSUFFICIENT_VRAM"
    recommended_method: str = "QLORA_4BIT"  # "QLORA_4BIT", "LORA_8BIT", "FULL_FINETUNE", "PROMPT_TUNING"
    recommended_batch_size: int = 1
    recommended_gradient_accumulation_steps: int = 4
    recommended_max_seq_length: int = 2048
    estimated_memory_usage_mb: int = 3450
    notes: str = "Hardware supports 4-bit QLoRA with rank r=16 and gradient checkpointing."


class TrainingLossStep(BaseModel):
    step: int
    epoch: float
    train_loss: float
    val_loss: Optional[float] = None
    learning_rate: float
    timestamp: str = Field(default_factory=_now)


class TrainingCheckpoint(BaseModel):
    checkpoint_id: str
    step: int
    epoch: float
    val_loss: float
    artifact_path: str
    is_best: bool = False
    created_at: str = Field(default_factory=_now)


class ModelBenchmarkDelta(BaseModel):
    base_model_score: float = 0.0
    trained_adapter_score: float = 0.0
    score_delta: float = 0.0
    safety_delta: float = 0.0
    correctness_delta: float = 0.0
    robustness_delta: float = 0.0
    tool_discipline_delta: float = 0.0
    fixed_failures: int = 0
    regressions_detected: int = 0
    recommendation: str = "RECOMMENDED_FOR_PROMOTION"  # "RECOMMENDED_FOR_PROMOTION", "REVIEW_REQUIRED", "REJECTED"


class TrainingJob(BaseModel):
    id: str = Field(default_factory=lambda: f"train-job-{uuid.uuid4().hex[:8]}")
    agent_id: str
    agent_name: str
    model_connection_id: str
    model_name: str = "Qwen2.5-Coder-7B"
    dataset_id: str
    dataset_name: str = "Curated SFT/DPO Dataset"
    
    # Training Setup
    training_method: str = "QLORA_4BIT"  # "QLORA_4BIT", "LORA_8BIT", "DPO", "FULL_FINETUNE"
    learning_rate: float = 2e-4
    epochs: int = 3
    lora_r: int = 16
    lora_alpha: int = 32
    batch_size: int = 1
    gradient_accumulation_steps: int = 4
    
    # Status & Progress
    # CREATED | PREFLIGHT | STAGING_DATA | TRAINING | VALIDATING | REGISTERING | BENCHMARKING | COMPLETED | FAILED | CANCELLED
    status: str = "CREATED"
    current_step_description: str = "Job created, awaiting preflight..."
    current_epoch: int = 0
    total_epochs: int = 3
    current_step: int = 0
    total_steps: int = 150
    progress_percentage: float = 0.0
    
    # Hardware & Telemetry
    hardware_preflight: HardwarePreflight = Field(default_factory=HardwarePreflight)
    loss_history: List[TrainingLossStep] = Field(default_factory=list)
    checkpoints: List[TrainingCheckpoint] = Field(default_factory=list)
    best_loss: Optional[float] = None
    
    # Outcomes & Promotion
    resulting_model_version_id: Optional[str] = None
    benchmark_comparison: Optional[ModelBenchmarkDelta] = None
    is_promoted: bool = False
    error_message: Optional[str] = None
    
    created_at: str = Field(default_factory=_now)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class ModelVersionRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"mver-{uuid.uuid4().hex[:8]}")
    agent_id: str
    model_name: str
    version_label: str  # e.g., "v1.0-Base", "v1.1-QLoRA-Run1"
    base_model: str
    parent_version_id: Optional[str] = None
    adapter_type: str = "QLORA"  # "BASE", "QLORA", "LORA", "FULL"
    training_job_id: Optional[str] = None
    dataset_id: Optional[str] = None
    adapter_path: Optional[str] = None
    is_active: bool = False
    benchmark_score: float = 0.0
    created_at: str = Field(default_factory=_now)
