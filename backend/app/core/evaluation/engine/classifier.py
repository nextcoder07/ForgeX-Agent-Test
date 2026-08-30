"""
Failure Classifier Module.
Normalizes raw failure findings into the standardized taxonomy.
"""
from __future__ import annotations

from typing import List
from app.models.failure import FailureFinding
from app.core.evaluation.engine.base import FailureClassifier

VALID_TAXONOMY = {
    "incorrect_task_completion",
    "hallucination",
    "tool_misuse",
    "unauthorized_action",
    "prompt_injection",
    "unsafe_action",
    "missing_tool_handling",
    "tool_failure_handling",
    "excessive_tool_calls",
    "looping",
    "policy_violation",
    "sandbox_violation",
}

CATEGORY_MAP = {
    "unauthorized_tool_invocation": "unauthorized_action",
    "unauthorized_payout": "unauthorized_action",
    "incorrect_tool_arguments": "tool_misuse",
    "expected_tool_not_called": "incorrect_task_completion",
    "missing_expected_output": "incorrect_task_completion",
    "prohibited_output_detected": "policy_violation",
    "destructive_action_without_confirmation": "unsafe_action",
    "destructive_action_no_confirm": "unsafe_action",
    "prompt_injection_detected": "prompt_injection",
    "infinite_tool_loop": "looping",
    "timeout": "tool_failure_handling",
    "rate_limit": "tool_failure_handling",
    "http_500": "tool_failure_handling",
}

class RuleBasedFailureClassifier(FailureClassifier):
    def classify(self, raw_findings: List[FailureFinding]) -> List[FailureFinding]:
        """Maps finding categories to standard taxonomy."""
        classified_findings: List[FailureFinding] = []

        for f in raw_findings:
            if not f.category:
                f.category = "INCORRECT_TASK_COMPLETION"
            else:
                f.category = f.category.upper().strip().replace(" ", "_")
            classified_findings.append(f)

        return classified_findings

class MLFailureClassifier(FailureClassifier):
    """Placeholder for future ML-based classifier using historical trace data."""
    def classify(self, raw_findings: List[FailureFinding]) -> List[FailureFinding]:
        # Drop-in extension point for Stage 3 evaluation models
        return raw_findings
