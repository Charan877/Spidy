"""Agent Run Repository for SPIDY.

Handles persistent tracking of discrete agent executions per build.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.agents")


class AgentRepository:
    """Data access object for the agent_runs table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def create_agent_run(
        self,
        build_id: str,
        agent_name: str,
        task_id: Optional[str] = None,
        status: str = "WORKING",
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record the start of an agent run."""
        rid = run_id or f"run_{uuid.uuid4().hex[:12]}"
        now = current_utc_iso()
        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (
                    run_id, build_id, agent_name, task_id, status, started_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (rid, build_id, agent_name, task_id, status, now),
            )
        return {"run_id": rid, "build_id": build_id, "agent_name": agent_name, "status": status, "started_at": now}

    def finish_agent_run(
        self,
        run_id: str,
        status: str = "SUCCESS",
        duration: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """Record completion or failure of an agent run."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE agent_runs
                SET status = ?,
                    completed_at = ?,
                    duration = ?,
                    error_message = ?
                WHERE run_id = ?;
                """,
                (status, now, duration, error_message, run_id),
            )
            return cursor.rowcount > 0

    def get_runs_for_build(self, build_id: str) -> List[Dict[str, Any]]:
        """Retrieve all agent runs for a specific build."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM agent_runs WHERE build_id = ? ORDER BY started_at ASC;",
                (build_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
