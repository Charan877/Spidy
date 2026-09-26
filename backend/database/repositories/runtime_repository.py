"""Runtime Repository for SPIDY.

Handles persistent tracking of runtime sessions, process IDs, dynamic ports, and health.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.runtime")


class RuntimeRepository:
    """Data access object for the runtime_sessions table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def create_session(
        self,
        build_id: str,
        project_id: str,
        framework: Optional[str] = None,
        pid: Optional[int] = None,
        port: Optional[int] = None,
        url: Optional[str] = None,
        status: str = "RUNNING",
        health_status: Optional[str] = "HEALTHY",
        runtime_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record the launch of an isolated runtime session."""
        rid = runtime_id or f"rt_{uuid.uuid4().hex[:12]}"
        now = current_utc_iso()
        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_sessions (
                    runtime_id, build_id, project_id, framework,
                    pid, port, url, status, started_at, health_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (rid, build_id, project_id, framework, pid, port, url, status, now, health_status),
            )
        return {
            "runtime_id": rid,
            "build_id": build_id,
            "project_id": project_id,
            "framework": framework,
            "pid": pid,
            "port": port,
            "url": url,
            "status": status,
            "started_at": now,
            "health_status": health_status,
        }

    def update_session(
        self,
        runtime_id: str,
        status: Optional[str] = None,
        health_status: Optional[str] = None,
        port: Optional[int] = None,
        url: Optional[str] = None,
    ) -> bool:
        """Update runtime session metrics dynamically."""
        updates = []
        params = []
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if health_status is not None:
            updates.append("health_status = ?")
            params.append(health_status)
        if port is not None:
            updates.append("port = ?")
            params.append(port)
        if url is not None:
            updates.append("url = ?")
            params.append(url)

        if not updates:
            return False

        params.append(runtime_id)
        query = f"UPDATE runtime_sessions SET {', '.join(updates)} WHERE runtime_id = ?;"
        with self.factory.connect() as conn:
            cursor = conn.execute(query, tuple(params))
            return cursor.rowcount > 0

    def close_session(
        self,
        runtime_id: str,
        status: str = "STOPPED",
        health_status: Optional[str] = None,
    ) -> bool:
        """Mark a runtime session as terminated."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE runtime_sessions
                SET status = ?,
                    stopped_at = ?,
                    health_status = COALESCE(?, health_status)
                WHERE runtime_id = ?;
                """,
                (status, now, health_status, runtime_id),
            )
            return cursor.rowcount > 0

    def get_sessions_for_build(self, build_id: str) -> List[Dict[str, Any]]:
        """Retrieve all runtime sessions for a specific build."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM runtime_sessions WHERE build_id = ? ORDER BY started_at DESC;",
                (build_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_latest_session(self, build_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the latest runtime session for a build."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM runtime_sessions WHERE build_id = ? ORDER BY started_at DESC LIMIT 1;",
                (build_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
