"""Build Repository for SPIDY.

Handles persistent tracking of build lifecycles and execution outcomes in SQLite.
"""

import logging
from typing import Any, Dict, List, Optional

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.builds")


class BuildRepository:
    """Data access object for the builds table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def create_build(
        self,
        build_id: str,
        project_id: str,
        requirement: str,
        estimated_duration: Optional[str] = None,
        status: str = "RUNNING",
    ) -> Dict[str, Any]:
        """Create a new build record."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO builds (
                    build_id, project_id, requirement, status,
                    started_at, estimated_duration
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (build_id, project_id, requirement, status, now, estimated_duration),
            )
        return self.get_build(build_id)

    def get_build(self, build_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve build record by ID."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM builds WHERE build_id = ?;", (build_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_builds_for_project(self, project_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve builds for a given project, ordered from newest to oldest."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM builds WHERE project_id = ? ORDER BY started_at DESC LIMIT ?;",
                (project_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_builds(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent builds across all projects, joined with project name."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT b.*, p.name AS project_name, p.detected_stack
                FROM builds b
                LEFT JOIN projects p ON b.project_id = p.project_id
                ORDER BY b.started_at DESC LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_build_status(self, build_id: str, status: str) -> bool:
        """Update status of a build in progress."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "UPDATE builds SET status = ? WHERE build_id = ?;",
                (status, build_id),
            )
            return cursor.rowcount > 0

    def finish_build(
        self,
        build_id: str,
        status: str,
        duration: Optional[float] = None,
        final_result: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """Mark a build as complete or failed with final metrics."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE builds
                SET status = ?,
                    completed_at = ?,
                    duration = ?,
                    final_result = ?,
                    failure_reason = ?
                WHERE build_id = ?;
                """,
                (status, now, duration, final_result, failure_reason, build_id),
            )
            return cursor.rowcount > 0

    def get_in_progress_builds(self) -> List[Dict[str, Any]]:
        """Retrieve all builds currently recorded as in-progress (RUNNING, BUILDING, IN_PROGRESS)."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT b.*, p.name AS project_name, p.detected_stack, p.workspace_path
                FROM builds b
                LEFT JOIN projects p ON b.project_id = p.project_id
                WHERE b.status IN ('RUNNING', 'BUILDING', 'IN_PROGRESS')
                ORDER BY b.started_at DESC;
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def mark_interrupted(self, build_id: str, reason: str = "Build interrupted unexpectedly") -> bool:
        """Mark an in-progress build as INTERRUPTED with timestamp and reason."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE builds
                SET status = 'INTERRUPTED',
                    completed_at = ?,
                    failure_reason = ?
                WHERE build_id = ? AND status IN ('RUNNING', 'BUILDING', 'IN_PROGRESS');
                """,
                (now, reason, build_id),
            )
            return cursor.rowcount > 0

