"""Project State module for NOVA Code Lab.

Tracks project context, requirements, task dependency graph, lifecycle state machine,
generation gates, active agent, progress calculation, and verification.
"""

from dataclasses import dataclass, field
import datetime
import time
from typing import Dict, List, Optional, Set


@dataclass
class Task:
    id: str
    title: str
    phase: str
    status: str = "QUEUED"  # "QUEUED", "READY", "RUNNING", "RECOVERING", "RETRYING", "SUCCESS", "FAILED", "BLOCKED", "SKIPPED", "CANCELLED", "pending", "completed"
    agent_assigned: str = "Orchestrator"
    file_path: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    retry_count: int = 0
    recovery_attempt: int = 0
    validation_result: Optional[Dict[str, Any]] = None
    is_required: bool = True
    build_id: str = ""
    project_id: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "phase": self.phase,
            "status": self.status,
            "agent_assigned": self.agent_assigned,
            "file_path": self.file_path,
            "dependencies": self.dependencies,
            "blocked_reason": self.blocked_reason,
            "result": self.result,
            "error": self.error,
            "provider": self.provider,
            "retry_count": self.retry_count,
            "recovery_attempt": self.recovery_attempt,
            "validation_result": self.validation_result,
            "is_required": self.is_required,
            "build_id": self.build_id,
            "project_id": self.project_id,
        }

    @classmethod
    def from_dict(cls, d: dict):
        filtered = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)


@dataclass
class ActivityLog:
    timestamp: str
    message: str
    level: str = "ok"  # "ok", "run", "bad", "dim"

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "message": self.message,
            "level": self.level,
        }


PHASES = [
    "DISCOVER",
    "PLAN",
    "ARCHITECT",
    "BUILD",
    "RUN",
    "TEST",
    "DEBUG",
    "REVIEW",
    "DOCUMENT",
    "COMPLETE",
]

PROJECT_STATES = [
    "INTAKE",
    "CLARIFYING",
    "PLANNING",
    "ARCHITECTING",
    "GENERATING",
    "GENERATED",
    "BUILDING",
    "BUILT",
    "PROCESS_STARTED",
    "PORT_DETECTED",
    "SERVER_READY",
    "HTTP_RESPONSIVE",
    "APPLICATION_VERIFIED",
    "RUNNING",
    "TESTING",
    "DEBUGGING",
    "REVIEWING",
    "DOCUMENTING",
    "VERIFYING",
    "SUCCESS",
    "FAILED",
    "RECOVERING",
    "BLOCKED",
    "WAITING_FOR_USER",
]


class ProjectState:
    """Holds complete, real-time application state for a project build."""

    def __init__(self, goal: str = "", selected_language: str = "Auto Detect"):
        self.project_name: str = "SPIDY Project"
        self.project_id: str = "spidy-default"
        self.build_id: str = ""
        self.task_graph_id: str = ""
        self.active_context: Optional[Any] = None
        self.db_manager: Optional[Any] = None
        self.conversation_id: str = ""
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_classification: str = "NEW_PROJECT"
        self.fullstack_contract: Dict[str, Any] = {}
        self.architecture_contract: Optional[Dict[str, Any]] = None
        self.frontend_url: Optional[str] = None
        self.frontend_port: Optional[int] = None
        self.frontend_pid: Optional[int] = None
        self.backend_url: Optional[str] = None
        self.backend_port: Optional[int] = None
        self.backend_pid: Optional[int] = None
        self.test_crud_endpoint: str = "/api/items"
        self.test_crud_payload: Dict[str, Any] = {}
        self.known_issues: List[str] = []
        self.reviewer_verdict: Optional[str] = None
        self.files_affected: List[str] = []
        self.goal: str = goal
        self.original_goal: str = goal
        self.requirements: str = goal
        self.detected_language: str = "Python"
        self.selected_language: str = selected_language
        self.effective_language: str = "Python"
        self.architecture_summary: str = ""
        self.tech_stack: List[str] = []
        self.project_spec: Dict = {}
        self.clarifying_questions: List[Dict[str, str]] = []
        self.clarification_answers: Dict[str, str] = {}
        self.user_approved: bool = False

        # Lifecycle state machine & Phase
        self.current_phase: str = "DISCOVER"
        self.project_state: str = "INTAKE"
        self.state_transition_history: List[Dict[str, str]] = []
        self.active_agent: str = "Orchestrator"
        self.active_agent_status: str = "READY"  # READY, WORKING, SUCCESS, FAILURE, BLOCKED
        self.current_task_description: str = "Awaiting prompt..."
        self.current_file_target: str = ""
        self.tasks: List[Task] = []
        self.files: Dict[str, str] = {}  # relative path -> content
        self.activity_feed: List[ActivityLog] = []
        self.errors: List[str] = []
        self.is_running: bool = False

        # Generation Gate & Preconditions
        self.project_generation_status: str = "NOT_STARTED"  # NOT_STARTED, GENERATING, GENERATED, GENERATION_FAILED
        self.is_project_generated: bool = False
        self.failure_type: Optional[str] = None  # PRECONDITION_FAILURE, AGENT_FAILURE, PROJECT_GENERATION_FAILURE, RUNTIME_FAILURE, TEST_FAILURE, USER_INPUT_REQUIRED
        self.recovery_attempts: int = 0

        # Runtime & Live Preview tracking
        self.project_type: str = "General Software Project"
        self.runtime_type: str = "api"  # api, web, fullstack, cli, library
        self.runtime_targets: List[Dict[str, Any]] = []
        self.is_web_project: bool = False
        self.runtime_status: str = "NOT_STARTED"  # NOT_STARTED, STARTING, WAITING_FOR_READY, VERIFYING, RUNNING, RECOVERING, FAILED, STOPPED
        self.runtime_command: str = ""
        self.runtime_cwd: Optional[str] = None
        self.runtime_pid: Optional[int] = None
        self.runtime_port: Optional[int] = None
        self.runtime_url: Optional[str] = None
        self.runtime_logs: str = ""
        self.is_app_verified: bool = False
        self.runtime_verification_steps: List[str] = []

        # Project outcome & granular verification gates
        self.project_success: bool = False
        self.failure_reason: Optional[str] = None
        self.failure_classification: Optional[str] = None
        self.verification_gates: Dict[str, bool] = {
            "build": False,
            "process": False,
            "port": False,
            "server": False,
            "http": False,
            "application": False,
        }

        # Build timing & dynamic estimation tracking
        self.build_start_time: Optional[float] = None
        self.build_end_time: Optional[float] = None
        self.estimated_duration_str: str = "~8-12 MIN"
        self.estimated_remaining_str: str = "~8-12 MIN"
        self.estimated_complexity: str = "HIGH"
        self.estimated_confidence: str = "MEDIUM"
        self.actual_duration_str: Optional[str] = None

    @property
    def elapsed_seconds(self) -> float:
        if not self.build_start_time:
            return 0.0
        end = self.build_end_time or time.time()
        return max(0.0, end - self.build_start_time)

    @property
    def formatted_elapsed(self) -> str:
        secs = int(self.elapsed_seconds)
        mins = secs // 60
        rem_sec = secs % 60
        return f"{mins:02d}:{rem_sec:02d}"

    @property
    def agent_count(self) -> int:
        if not self.tasks:
            return 5
        agents = {t.agent_assigned for t in self.tasks if t.agent_assigned}
        return max(len(agents), 1)

    @property
    def progress_percentage(self) -> int:
        if not self.tasks:
            return 100 if self.current_phase == "COMPLETE" else 0
        completed = sum(1 for t in self.tasks if t.status in ("SUCCESS", "completed"))
        return int(round((completed / len(self.tasks)) * 100))

    @property
    def task_counts(self) -> dict:
        completed = sum(1 for t in self.tasks if t.status in ("SUCCESS", "completed"))
        active = sum(1 for t in self.tasks if t.status in ("RUNNING", "active"))
        blocked = sum(1 for t in self.tasks if t.status == "BLOCKED")
        remaining = sum(1 for t in self.tasks if t.status in ("QUEUED", "READY", "BLOCKED", "pending"))
        total = len(self.tasks)
        return {
            "completed": completed,
            "active": active,
            "blocked": blocked,
            "remaining": remaining,
            "total": total,
        }

    def transition_to(self, new_state: str, reason: str = "") -> bool:
        """Validate and apply a lifecycle state transition."""
        # Prohibit invalid transitions
        if self.project_state in ("PLANNING", "ARCHITECTING", "INTAKE") and new_state in ("DEBUGGING", "TESTING", "RUNNING"):
            self.add_activity(f"Invalid state transition rejected: {self.project_state} -> {new_state}. Prerequisites missing.", level="bad")
            return False

        if new_state in ("RUNNING", "TESTING") and not self.is_project_generated:
            self.add_activity(f"Invalid state transition rejected: cannot enter {new_state} before project is GENERATED.", level="bad")
            return False

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.state_transition_history.append({"from": self.project_state, "to": new_state, "reason": reason, "time": ts})
        self.project_state = new_state
        return True

    def is_task_ready(self, task: Task) -> bool:
        """Verify that all prerequisite task dependencies have succeeded."""
        if not task.dependencies:
            return True
        completed_ids = {t.id for t in self.tasks if t.status in ("SUCCESS", "completed")}
        return all(dep_id in completed_ids for dep_id in task.dependencies)

    def add_activity(self, message: str, level: str = "ok") -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.activity_feed.append(ActivityLog(timestamp=ts, message=message, level=level))

    def add_task(
        self,
        task_id: str,
        title: str,
        phase: str,
        agent: str = "Developer Agent",
        file_path: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        is_required: bool = True,
        build_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        bid = build_id or getattr(self, "build_id", "")
        pid = project_id or getattr(self, "project_id", "")
        self.tasks.append(
            Task(
                id=task_id,
                title=title,
                phase=phase,
                status="QUEUED",
                agent_assigned=agent,
                file_path=file_path,
                dependencies=dependencies or [],
                is_required=is_required,
                build_id=bid,
                project_id=pid,
            )
        )

    def has_failed_required_tasks(self) -> bool:
        """Check if any task marked as required in the current build has failed."""
        current_build = getattr(self, "build_id", None)
        return any(
            t.status == "FAILED"
            and getattr(t, "is_required", True)
            and (not current_build or not getattr(t, "build_id", None) or t.build_id == current_build)
            for t in self.tasks
        )

    def set_active_task(self, task_id: str) -> None:
        for t in self.tasks:
            if t.id == task_id:
                t.status = "RUNNING"
                self.current_task_description = t.title
                self.active_agent = t.agent_assigned
                self.active_agent_status = "WORKING"
                if t.file_path:
                    self.current_file_target = t.file_path
            elif t.status in ("RUNNING", "active"):
                t.status = "QUEUED"

    def recover_task(self, task_id: str, reason: str = "") -> None:
        """Transition task to RECOVERING state."""
        for t in self.tasks:
            if t.id == task_id:
                t.status = "RECOVERING"
                t.blocked_reason = None
                self.active_agent = t.agent_assigned
                self.active_agent_status = "WORKING"
                self.add_activity(f"Task {task_id} ({t.title}) -> RECOVERING: {reason}", level="run")
                break

    def retry_task(self, task_id: str, attempt: int) -> None:
        """Transition task to RETRYING state with bounded attempt count."""
        for t in self.tasks:
            if t.id == task_id:
                t.status = "RETRYING"
                t.retry_count = attempt
                t.recovery_attempt = attempt
                self.active_agent = t.agent_assigned
                self.active_agent_status = "WORKING"
                self.add_activity(f"Task {task_id} ({t.title}) -> RETRYING (Attempt {attempt}/3)...", level="run")
                break

    def complete_task(
        self,
        task_id: str,
        result: Optional[str] = None,
        agent_result: Optional[Any] = None,
    ) -> None:
        """Transition task to SUCCESS state, clearing failure status and unblocking dependents."""
        for t in self.tasks:
            if t.id == task_id:
                was_recovering = t.status in ("FAILED", "RECOVERING", "RETRYING")
                t.status = "SUCCESS"
                t.result = result or (getattr(agent_result, "result", None) if agent_result else "Task completed successfully")
                t.error = None
                t.blocked_reason = None
                if agent_result:
                    t.provider = getattr(agent_result, "provider", t.provider)
                    t.validation_result = getattr(agent_result, "validation_result", t.validation_result)
                    t.recovery_attempt = getattr(agent_result, "recovery_attempt", t.recovery_attempt)

                if was_recovering:
                    self.add_activity(f"Task {task_id} ({t.title}) RECOVERED -> SUCCESS (Validated)", level="ok")
                else:
                    self.add_activity(f"Task {task_id} completed: {t.title}", level="ok")
                break

    def fail_task(
        self,
        task_id: str,
        error_msg: str,
        agent_result: Optional[Any] = None,
    ) -> None:
        """Transition task to FAILED state."""
        for t in self.tasks:
            if t.id == task_id:
                t.status = "FAILED"
                t.result = error_msg
                t.error = error_msg
                if agent_result:
                    t.provider = getattr(agent_result, "provider", t.provider)
                    t.recovery_attempt = getattr(agent_result, "recovery_attempt", t.recovery_attempt)
                    t.validation_result = getattr(agent_result, "validation_result", t.validation_result)
                break
        self.errors.append(error_msg)
        self.active_agent_status = "FAILURE"
        self.add_activity(f"Task {task_id} failed: {error_msg}", level="bad")

    def recalculate_task_graph(self) -> List[str]:
        """Re-evaluate task dependency graph. Unblock tasks whose prerequisites have succeeded."""
        unblocked = []
        completed_ids = {t.id for t in self.tasks if t.status in ("SUCCESS", "completed")}
        for t in self.tasks:
            if t.status == "BLOCKED":
                if not t.dependencies or all(dep in completed_ids for dep in t.dependencies):
                    t.status = "QUEUED"
                    t.blocked_reason = None
                    unblocked.append(t.id)
                    self.add_activity(f"Task {t.id} ({t.title}) UNBLOCKED after dependency resolution.", level="ok")
        return unblocked

    def block_task(self, task_id: str, reason: str) -> None:
        for t in self.tasks:
            if t.id == task_id:
                t.status = "BLOCKED"
                t.blocked_reason = reason
        self.active_agent_status = "BLOCKED"
        self.add_activity(f"Task {task_id} BLOCKED: {reason}", level="dim")

    def fail(self, error_msg: str, classification: Optional[str] = None) -> None:
        """Mark project execution as failed with explicit reason and classification."""
        self.errors.append(error_msg)
        self.current_phase = "FAILED"
        self.project_state = "FAILED"
        self.failure_reason = error_msg
        self.failure_classification = classification or "EXECUTION_FAILURE"
        self.active_agent_status = "FAILURE"
        self.is_running = False
        self.add_activity(f"Execution failed: {error_msg}", level="bad")

    def interrupt(self, reason: str = "Execution interrupted by user or server restart") -> None:
        """Mark project execution as interrupted."""
        self.errors.append(reason)
        self.current_phase = "FAILED"
        self.project_state = "FAILED"
        self.failure_reason = reason
        self.failure_classification = "EXECUTION_INTERRUPTED"
        self.active_agent_status = "FAILURE"
        self.is_running = False
        self.add_activity(f"Execution interrupted: {reason}", level="bad")

    def reset(

        self,
        new_goal: str = "",
        language: str = "Auto Detect",
        project_id: Optional[str] = None,
        build_id: Optional[str] = None,
    ) -> None:
        self.__init__(goal=new_goal, selected_language=language)
        if project_id:
            self.project_id = project_id
        if build_id:
            self.build_id = build_id
            self.task_graph_id = f"tg_{build_id}"

    def to_dict(self) -> dict:
        """Serialize complete project state to dictionary for WebSocket and REST APIs."""
        completed_count = sum(1 for t in self.tasks if t.status in ("SUCCESS", "completed"))
        total_count = len(self.tasks)
        pct = int((completed_count / total_count * 100)) if total_count > 0 else 0

        return {
            "project_name": self.project_name,
            "project_id": getattr(self, "project_id", "spidy-default"),
            "build_id": getattr(self, "build_id", ""),
            "task_graph_id": getattr(self, "task_graph_id", ""),
            "conversation_id": getattr(self, "conversation_id", ""),
            "current_classification": getattr(self, "current_classification", "NEW_PROJECT"),
            "fullstack_contract": getattr(self, "fullstack_contract", {}),
            "architecture_contract": getattr(self, "architecture_contract", None),
            "frontend_url": getattr(self, "frontend_url", None),
            "frontend_port": getattr(self, "frontend_port", None),
            "frontend_pid": getattr(self, "frontend_pid", None),
            "backend_url": getattr(self, "backend_url", None),
            "backend_port": getattr(self, "backend_port", None),
            "backend_pid": getattr(self, "backend_pid", None),
            "known_issues": getattr(self, "known_issues", []),
            "reviewer_verdict": getattr(self, "reviewer_verdict", None),
            "files_affected": getattr(self, "files_affected", []),
            "has_failed_required_tasks": self.has_failed_required_tasks(),
            "goal": self.goal,
            "detected_language": self.detected_language,
            "selected_language": self.selected_language,
            "effective_language": self.effective_language,
            "architecture_summary": self.architecture_summary,
            "tech_stack": self.tech_stack,
            "clarifying_questions": self.clarifying_questions,
            "clarification_answers": self.clarification_answers,
            "user_approved": self.user_approved,
            "current_phase": self.current_phase,
            "project_state": self.project_state,
            "active_agent": self.active_agent,
            "active_agent_status": self.active_agent_status,
            "current_task_description": self.current_task_description,
            "current_file_target": self.current_file_target,
            "tasks": [t.to_dict() for t in self.tasks],
            "tasks_completed": completed_count,
            "tasks_total": total_count,
            "progress_percent": pct,
            "activity_feed": [a.to_dict() for a in self.activity_feed[-80:]],
            "errors": self.errors[-10:],
            "is_running": self.is_running,
            "project_generation_status": self.project_generation_status,
            "is_project_generated": self.is_project_generated,
            "recovery_attempts": self.recovery_attempts,
            "project_type": self.project_type,
            "runtime_type": self.runtime_type,
            "runtime_targets": self.runtime_targets,
            "is_web_project": self.is_web_project,
            "runtime_status": self.runtime_status,
            "runtime_command": self.runtime_command,
            "runtime_pid": self.runtime_pid,
            "runtime_port": self.runtime_port,
            "runtime_url": self.runtime_url,
            "runtime_logs": self.runtime_logs[-2000:],
            "is_app_verified": self.is_app_verified,
            "verification_gates": self.verification_gates,
            "project_success": self.project_success,
            "failure_reason": self.failure_reason,
            "failure_classification": self.failure_classification,
            "elapsed_seconds": self.elapsed_seconds,
            "formatted_elapsed": self.formatted_elapsed,
            "estimated_duration_str": self.estimated_duration_str,
            "estimated_remaining_str": self.estimated_remaining_str,
            "estimated_complexity": self.estimated_complexity,
            "estimated_confidence": self.estimated_confidence,
            "actual_duration_str": self.actual_duration_str,
            "files_count": len(self.files),
            "files_list": list(self.files.keys()),
        }
