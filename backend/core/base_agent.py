"""Base Agent interface for NOVA Code Lab.

Defines standard agent execution lifecycle: START, WORKING, SUCCESS, FAILURE.
"""

import time
from typing import Any, Callable, Dict, Optional
from backend.core.project_state import ProjectState


class BaseAgent:
    """Base class for all AI agents in NOVA Code Lab."""

    def __init__(self, name: str, role: str, default_llm_role: str = "general"):
        self.name = name
        self.role = role
        self.default_llm_role = default_llm_role
        self.status = "READY"  # READY, WORKING, SUCCESS, FAILURE

    def generate(
        self,
        messages: Any,
        system_prompt: Optional[str] = None,
        role: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """Execute completion request through central ModelRouter without direct provider calls."""
        from backend.core.llm.model_router import get_model_router
        router = get_model_router()
        target_role = role or self.default_llm_role
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        return router.generate_text(
            role=target_role,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def set_status(self, status: str, state: ProjectState) -> None:
        self.status = status
        state.active_agent = self.name
        state.active_agent_status = status

    def execute(
        self,
        state: ProjectState,
        action_fn: Callable[..., Any],
        task_id: Optional[str] = None,
        *args,
        **kwargs,
    ) -> Any:
        """Standardized lifecycle execution wrapper around an agent action."""
        if hasattr(state, "can_execute_engineering") and not state.can_execute_engineering():
            block_msg = f"{self.name} blocked: execution prohibited while awaiting user confirmation."
            state.add_activity(block_msg, level="bad")
            if task_id:
                state.block_task(task_id, "Awaiting user confirmation")
            return None

        self.set_status("WORKING", state)
        state.add_activity(f"{self.name} activated ({self.role})", level="run")

        if task_id:
            state.set_active_task(task_id)

        start_t = time.time()
        db_manager = getattr(state, "db_manager", None)
        build_id = getattr(state, "build_id", None)
        run_id = None
        if db_manager and build_id:
            try:
                run_id = db_manager.sync_agent_run_start(
                    build_id=build_id,
                    agent_name=self.name,
                    task_id=task_id,
                )
            except Exception:
                pass

        try:
            result = action_fn(state, *args, **kwargs)
            if hasattr(state, "is_awaiting_confirmation") and state.is_awaiting_confirmation():
                self.set_status("READY", state)
                return result

            self.set_status("SUCCESS", state)
            state.add_activity(f"{self.name} completed task successfully", level="ok")
            if task_id:
                state.complete_task(task_id)
            if db_manager and run_id:
                try:
                    db_manager.sync_agent_run_finish(
                        run_id=run_id,
                        status="SUCCESS",
                        duration=time.time() - start_t,
                    )
                except Exception:
                    pass
            return result
        except Exception as exc:
            self.set_status("FAILURE", state)
            error_msg = f"{self.name} failed: {exc}"
            state.add_activity(error_msg, level="bad")
            if task_id:
                state.fail_task(task_id, str(exc))
            if db_manager and run_id:
                try:
                    db_manager.sync_agent_run_finish(
                        run_id=run_id,
                        status="FAILURE",
                        duration=time.time() - start_t,
                        error_message=str(exc),
                    )
                except Exception:
                    pass
            raise RuntimeError(error_msg) from exc

