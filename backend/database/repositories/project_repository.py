"""Project Repository for SPIDY.

Handles persistent CRUD operations for discrete projects in SQLite.
"""

import logging
import sqlite3
from typing import Any, Dict, List, Optional

from backend.database.connection import current_utc_iso

logger = logging.getLogger("spidy.database.projects")


class ProjectRepository:
    """Data access object for the projects table."""

    def __init__(self, connection_factory):
        self.factory = connection_factory

    def ensure_project(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
        workspace_path: Optional[str] = None,
        detected_stack: Optional[str] = None,
        status: str = "IDLE",
    ) -> Dict[str, Any]:
        """Ensure a project record exists; creates if missing, updates updated_at if present."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?;", (project_id,)
            )
            existing = cursor.fetchone()
            now = current_utc_iso()

            if existing:
                conn.execute(
                    """
                    UPDATE projects
                    SET name = COALESCE(?, name),
                        description = COALESCE(?, description),
                        workspace_path = COALESCE(?, workspace_path),
                        detected_stack = COALESCE(?, detected_stack),
                        status = COALESCE(?, status),
                        updated_at = ?
                    WHERE project_id = ?;
                    """,
                    (name, description, workspace_path, detected_stack, status, now, project_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO projects (
                        project_id, name, description, workspace_path,
                        detected_stack, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (project_id, name, description or "", workspace_path or "", detected_stack or "", status, now, now),
                )

        return self.get_project(project_id)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve project record by ID including its build count."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT p.*, (SELECT COUNT(*) FROM builds b WHERE b.project_id = p.project_id) AS build_count
                FROM projects p
                WHERE p.project_id = ?;
                """,
                (project_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_projects(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all projects ordered by most recently updated, including build counts."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                """
                SELECT p.*, (SELECT COUNT(*) FROM builds b WHERE b.project_id = p.project_id) AS build_count
                FROM projects p
                ORDER BY p.updated_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_project_status(
        self,
        project_id: str,
        status: str,
        detected_stack: Optional[str] = None,
    ) -> bool:
        """Update status and stack for a project."""
        now = current_utc_iso()
        with self.factory.connect() as conn:
            params = [status, now]
            query = "UPDATE projects SET status = ?, updated_at = ?"
            if detected_stack is not None:
                query += ", detected_stack = ?"
                params.append(detected_stack)
            query += " WHERE project_id = ?;"
            params.append(project_id)

            cursor = conn.execute(query, tuple(params))
            return cursor.rowcount > 0

    def update_project_contract(
        self,
        project_id: str,
        architecture_summary: Optional[str] = None,
        contract_json: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> bool:
        """Update architecture summary, contract JSON, and conversation ID for project."""
        now = current_utc_iso()
        fields = ["updated_at = ?"]
        params: List[Any] = [now]

        if architecture_summary is not None:
            fields.append("architecture_summary = ?")
            params.append(architecture_summary)
        if contract_json is not None:
            fields.append("contract_json = ?")
            params.append(contract_json)
        if conversation_id is not None:
            fields.append("conversation_id = ?")
            params.append(conversation_id)

        params.append(project_id)
        query = f"UPDATE projects SET {', '.join(fields)} WHERE project_id = ?;"

        with self.factory.connect() as conn:
            cursor = conn.execute(query, tuple(params))
            return cursor.rowcount > 0

    def delete_project(self, project_id: str) -> bool:
        """Delete project and cascading children."""
        with self.factory.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE project_id = ?;", (project_id,)
            )
            return cursor.rowcount > 0
