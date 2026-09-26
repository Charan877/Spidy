"""Message Repository for SPIDY.

Handles persistent CRUD operations for conversational messages linked to projects.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.messages")


class MessageRepository:
    """Data access object for the messages table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def save_message(
        self,
        project_id: str,
        role: str,
        content: str,
        classification: Optional[str] = None,
        build_id: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a new conversational message."""
        mid = message_id or f"msg_{uuid.uuid4().hex[:12]}"
        now = current_utc_iso()

        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, project_id, build_id, role,
                    content, classification, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (mid, project_id, build_id, role, content, classification, now),
            )

        return {
            "message_id": mid,
            "project_id": project_id,
            "build_id": build_id,
            "role": role,
            "content": content,
            "classification": classification,
            "timestamp": now,
        }

    def get_messages_for_project(
        self, project_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve conversational history for a project ordered chronologically."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM messages
                WHERE project_id = ?
                ORDER BY timestamp ASC
                LIMIT ?;
                """,
                (project_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_messages(
        self, project_id: str, count: int = 10
    ) -> List[Dict[str, Any]]:
        """Retrieve recent messages for context injection."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages
                    WHERE project_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ) ORDER BY timestamp ASC;
                """,
                (project_id, count),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_messages_for_build(self, build_id: str) -> List[Dict[str, Any]]:
        """Retrieve messages linked to a specific build."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM messages
                WHERE build_id = ?
                ORDER BY timestamp ASC;
                """,
                (build_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
