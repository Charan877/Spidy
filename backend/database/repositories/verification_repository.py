"""Verification Repository for SPIDY.

Handles persistent records for the six-gate convergence verification matrix.
"""

import logging
from typing import Any, Dict, List, Optional
import uuid

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.verification")


class VerificationRepository:
    """Data access object for the verification table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def record_gate_result(
        self,
        build_id: str,
        gate_name: str,
        status: str,
        message: Optional[str] = None,
        verification_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record validation outcome for a specific verification gate."""
        vid = verification_id or f"ver_{uuid.uuid4().hex[:12]}"
        now = current_utc_iso()
        with self.factory.connect() as conn:
            conn.execute(
                """
                INSERT INTO verification (
                    verification_id, build_id, gate_name, status, message, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (vid, build_id, gate_name, status, message, now),
            )
        return {
            "verification_id": vid,
            "build_id": build_id,
            "gate_name": gate_name,
            "status": status,
            "message": message,
            "timestamp": now,
        }

    def get_gates_for_build(self, build_id: str) -> List[Dict[str, Any]]:
        """Retrieve all verification gate results for a build."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM verification WHERE build_id = ? ORDER BY timestamp ASC;",
                (build_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
