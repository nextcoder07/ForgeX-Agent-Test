"""
Abstract Base Classes for Stage 3 Evaluation Pipeline.
Provides interfaces for Evaluator, FailureClassifier, and ScenarioScorer.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.models.agent import AgentRecord
from app.models.scenario import Scenario
from app.models.execution import ExecutionTrace
from app.models.failure import RunVerdict, FailureFinding
from app.models.evaluation import ReliabilityScorecard

class Evaluator(ABC):
    @abstractmethod
    async def evaluate(
        self,
        agent: AgentRecord,
        scenario: Scenario,
        trace: ExecutionTrace,
        counterfactual_trace: Optional[ExecutionTrace] = None
    ) -> RunVerdict:
        """Evaluates an execution trace against the scenario parameters."""
        pass

class FailureClassifier(ABC):
    @abstractmethod
    def classify(self, raw_findings: List[FailureFinding]) -> List[FailureFinding]:
        """Normalizes and maps raw failures into predefined taxonomies."""
        pass

class ScenarioScorer(ABC):
    @abstractmethod
    def score(
        self,
        evaluation_id: str,
        agent: AgentRecord,
        verdicts: List[RunVerdict]
    ) -> ReliabilityScorecard:
        """Calculates safety, correctness, capability, and composite scores."""
        pass
