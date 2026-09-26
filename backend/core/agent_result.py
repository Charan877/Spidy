"""Agent Result Contract for SPIDY.

Defines the standardized result contract between agents, providers,
and the orchestrator for task execution, validation, and recovery.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentResult:
    """Standardized result contract returned by agent execution and task runs."""

    status: str  # "SUCCESS", "FAILED", "RECOVERED", "SKIPPED"
    task_id: str
    project_id: str = ""
    build_id: str = ""
    success: bool = True
    artifact_path: Optional[str] = None
    provider: str = "Unknown"
    provider_attempts: int = 1
    error: Optional[str] = None
    recovery_attempt: int = 0
    validation_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResult":
        filtered = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**filtered)
