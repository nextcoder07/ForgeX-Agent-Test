"""
Side Effect Detector Engine.
Factually measures state differences between PreExecutionSnapshot and PostExecutionSnapshot / runtime events.
Does NOT judge whether changes were correct or allowed (Judgment is strictly deferred to Stage 3 Evaluation).
"""

from typing import Any, Dict, List
from app.models.execution import PreExecutionSnapshot, PostExecutionSnapshot, ExecutionAction


class SideEffectDetector:
    @staticmethod
    def detect_side_effects(
        pre_snapshot: PreExecutionSnapshot,
        post_snapshot: PostExecutionSnapshot,
        actions: List[ExecutionAction]
    ) -> Dict[str, Any]:
        """Detects actual state changes across filesystem, database, network, process, and external tools."""
        
        # 1. Filesystem Side Effects
        fs_changes = list(post_snapshot.modified_files)
        pre_files = pre_snapshot.filesystem_state
        post_files = post_snapshot.filesystem_state
        for fpath, post_val in post_files.items():
            if fpath not in pre_files or pre_files[fpath] != post_val:
                if fpath not in fs_changes:
                    fs_changes.append(fpath)

        # 2. Database Side Effects
        db_diffs = []
        pre_db = pre_snapshot.database_fixture_state
        post_db = post_snapshot.database_state
        for key, post_val in post_db.items():
            pre_val = pre_db.get(key)
            if pre_val != post_val:
                db_diffs.append({"resource": key, "before": pre_val, "after": post_val})

        # 3. External Tool / Network Side Effects
        external_tool_side_effects = [
            act.target for act in actions
            if (act.side_effect.get("detected") or act.side_effect_detected) and act.execution_result.get("executed", act.executed)
        ]

        total_side_effects = len(fs_changes) + len(db_diffs) + len(external_tool_side_effects)

        return {
            "side_effect_occurred": total_side_effects > 0,
            "total_side_effects_count": total_side_effects,
            "filesystem_changes": fs_changes,
            "database_diffs": db_diffs,
            "external_side_effects": external_tool_side_effects,
            "process_exit_code": post_snapshot.process_exit_code
        }
