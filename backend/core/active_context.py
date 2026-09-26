"""Active Project Context module for SPIDY.

Provides an authoritative, thread-safe context container encapsulating:
- project_id
- project_name
- conversation_id
- build_id
- task_graph_id
- workspace_path

Ensures strict isolation across project lifecycles, builds, and conversations.
"""

from dataclasses import dataclass
import threading
import time
from typing import Optional
import uuid


@dataclass
class ActiveProjectContext:
    project_id: str
    project_name: str
    conversation_id: str
    build_id: str
    task_graph_id: str
    workspace_path: str

    @classmethod
    def create_new(
        cls,
        project_name: str = "SPIDY Project",
        project_id: Optional[str] = None,
        build_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> "ActiveProjectContext":
        ts = int(time.time())
        pid = project_id or f"proj_{ts}_{uuid.uuid4().hex[:4]}"
        bid = build_id or f"bld_{ts}_{uuid.uuid4().hex[:6]}"
        cid = conversation_id or f"conv_{pid}_{uuid.uuid4().hex[:4]}"
        tgid = f"tg_{bid}"
        from backend.core.workspace_manager import WorkspaceManager
        ws = WorkspaceManager.for_project(pid)
        return cls(
            project_id=pid,
            project_name=project_name,
            conversation_id=cid,
            build_id=bid,
            task_graph_id=tgid,
            workspace_path=str(ws.root),
        )

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "conversation_id": self.conversation_id,
            "build_id": self.build_id,
            "task_graph_id": self.task_graph_id,
            "workspace_path": self.workspace_path,
        }


# Thread-safe global context registry
_current_context: Optional[ActiveProjectContext] = None
_context_lock = threading.Lock()


def get_active_context() -> Optional[ActiveProjectContext]:
    with _context_lock:
        return _current_context


def set_active_context(ctx: ActiveProjectContext) -> None:
    global _current_context
    with _context_lock:
        _current_context = ctx


def clear_active_context() -> None:
    global _current_context
    with _context_lock:
        _current_context = None
