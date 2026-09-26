"""Activity Repository for SPIDY.

Handles persistent activity logging and timeline events per build.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.activity")


class ActivityRepository:
    """Data access object for the activity table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def record_activity(
        self,
        build_id: str,
        message: str,
        event_type: str = "pipeline",
        agent: Optional[str] = None,
        status: Optional[str] = None,
        activity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an activity event for a build."""
        aid = activity_id or f"act_{uuid.uuid4().hex[:12]}"
        now = current_utc_iso()
        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO activity (
                    activity_id, build_id, timestamp, event_type, agent, message, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (aid, build_id, now, event_type, agent, message, status),
            )
        return {
            "activity_id": aid,
            "build_id": build_id,
            "timestamp": now,
            "event_type": event_type,
            "agent": agent,
            "message": message,
            "status": status,
        }

    def get_activities_for_build(self, build_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieve timeline activities for a build, ordered chronologically."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM activity WHERE build_id = ? ORDER BY timestamp ASC LIMIT ?;",
                (build_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
