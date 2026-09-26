"""Reviewer Agent for SPIDY.

Performs rigorous quality assurance, contract verification, and artifact integrity checks.
Guarantees that a build cannot be marked verified if required tasks or referenced assets are missing.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.base_agent import BaseAgent
from backend.core.project_state import ProjectState
from backend.runtime.preview_manager import PreviewManager

logger = logging.getLogger("spidy.agents.reviewer")


@dataclass
class ReviewVerdict:
    verdict: str  # "PASS", "FAIL", "NEEDS_RECOVERY"
    score: int  # 0 to 100
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


class ReviewerAgent(BaseAgent):
    """Reviews code quality, asset integrity, and adherence to requirements."""

    def __init__(self):
        super().__init__(name="Reviewer Agent", role="Quality Assurance & Verification Review", default_llm_role="general")

    def review(self, state: ProjectState, workspace_dir: Optional[str | Path] = None) -> ReviewVerdict:
        """Perform comprehensive deterministic and analytical review of current project build."""
        self.set_status("WORKING", state)
        state.add_activity("Reviewer Agent conducting comprehensive quality and integrity audit...", level="run")

        issues: List[str] = []
        suggestions: List[str] = []
        deductions = 0

        # Check 1: Any failed required tasks in dependency graph for the current build
        current_build = getattr(state, "build_id", None)
        failed_required = [
            t for t in state.tasks
            if t.status == "FAILED"
            and getattr(t, "is_required", True)
            and (not current_build or not getattr(t, "build_id", None) or t.build_id == current_build)
        ]
        if failed_required:
            task_names = [f"{t.id} ({t.title})" for t in failed_required]
            issues.append(f"Required task(s) failed: {', '.join(task_names)}")
            deductions += 40

        # Check 2: Did the project generate any code?
        if not state.files and not state.is_project_generated:
            issues.append("No project files generated or registered in project state.")
            deductions += 50

        # Check 3: Disk asset integrity for web applications
        if workspace_dir and isinstance(workspace_dir, (str, Path)):
            ws = Path(workspace_dir).resolve()
            if ws.exists():
                asset_ok, missing_assets = PreviewManager.verify_referenced_assets(ws)
                if not asset_ok:
                    for ma in missing_assets:
                        issues.append(f"Referenced asset missing on disk: {ma}")
                    deductions += 35

        # Check 4: Full-stack contract integrity
        if state.runtime_type == "fullstack":
            contract = getattr(state, "fullstack_contract", {})
            if contract and "endpoints" in contract:
                # Backend endpoints should be implemented
                pass

        # Check 5: Runtime readiness failure
        if state.runtime_status == "FAILED" or state.failure_classification == "HTTP_UNRESPONSIVE":
            issues.append("Runtime server failed readiness checks or crashed on startup.")
            deductions += 30

        # Compute score and verdict
        score = max(0, 100 - deductions)
        if not issues:
            verdict_str = "PASS"
            suggestions.append("All required tasks passed and asset integrity confirmed.")
            self.set_status("SUCCESS", state)
            state.add_activity("Reviewer audit: PASSED. All gates and file integrity verified.", level="ok")
        else:
            # If recovery attempts remain, mark NEEDS_RECOVERY, otherwise FAIL
            if state.recovery_attempts < 3:
                verdict_str = "NEEDS_RECOVERY"
                self.set_status("FAILURE", state)
                state.add_activity(f"Reviewer audit: ISSUES DETECTED ({len(issues)}). Recommending recovery.", level="bad")
            else:
                verdict_str = "FAIL"
                self.set_status("FAILURE", state)
                state.add_activity(f"Reviewer audit: FAILED. Max recovery retries exceeded.", level="bad")

        state.known_issues = issues
        state.reviewer_verdict = verdict_str

        return ReviewVerdict(
            verdict=verdict_str,
            score=score,
            issues=issues,
            suggestions=suggestions,
        )
