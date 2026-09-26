"""Database Manager for SPIDY.

Coordinates database lifecycle, schema initialization, and provides unified
access to Project, Build, Agent, Activity, Runtime, and Verification repositories.
Guarantees resilient persistence without interrupting real-time in-memory pipelines.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.database.connection import DatabaseConnectionFactory, get_default_db_path
from backend.database.repositories.activity_repository import ActivityRepository
from backend.database.repositories.agent_repository import AgentRepository
from backend.database.repositories.build_repository import BuildRepository
from backend.database.repositories.project_repository import ProjectRepository
from backend.database.repositories.runtime_repository import RuntimeRepository
from backend.database.repositories.verification_repository import VerificationRepository
from backend.database.repositories.message_repository import MessageRepository
from backend.database.schema import CURRENT_SCHEMA_VERSION, get_current_schema_version, initialize_schema

logger = logging.getLogger("spidy.database.manager")

_global_db_manager: Optional["DatabaseManager"] = None


class DatabaseManager:
    """Central interface coordinating SQLite persistence for SPIDY."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path).resolve() if db_path else get_default_db_path()
        self.factory = DatabaseConnectionFactory(self.db_path)

        # Repositories
        self.projects = ProjectRepository(self.factory)
        self.builds = BuildRepository(self.factory)
        self.agents = AgentRepository(self.factory)
        self.activity = ActivityRepository(self.factory)
        self.runtimes = RuntimeRepository(self.factory)
        self.verification = VerificationRepository(self.factory)
        self.messages = MessageRepository(self.factory)

        self._initialized = False

    def initialize(self) -> Tuple[bool, int]:
        """Automatically provision data directory and apply schema idempotently."""
        try:
            with self.factory.connect() as conn:
                upgraded, version = initialize_schema(conn)
                self._initialized = True
                logger.info(
                    f"SPIDY Database successfully initialized at {self.db_path} (schema v{version})."
                )
                return upgraded, version
        except Exception as exc:
            logger.error(f"Fatal error during database initialization: {exc}")
            raise

    def is_initialized(self) -> bool:
        """Check if schema is ready."""
        return self._initialized

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostic metrics on database health, schema, and record counts."""
        try:
            with self.factory.connect() as conn:
                version = get_current_schema_version(conn)
                cursor = conn.cursor()

                def count(table: str) -> int:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table};")
                        row = cursor.fetchone()
                        return row[0] if row else 0
                    except Exception:
                        return 0

                return {
                    "status": "HEALTHY",
                    "db_path": str(self.db_path),
                    "schema_version": version,
                    "target_version": CURRENT_SCHEMA_VERSION,
                    "counts": {
                        "projects": count("projects"),
                        "builds": count("builds"),
                        "agent_runs": count("agent_runs"),
                        "activities": count("activity"),
                        "runtime_sessions": count("runtime_sessions"),
                        "verification": count("verification"),
                        "messages": count("messages"),
                    },
                }
        except Exception as exc:
            return {
                "status": "DEGRADED",
                "db_path": str(self.db_path),
                "error": str(exc),
            }

    # =========================================================================
    # Resilient State Synchronization Helpers
    # =========================================================================

    def sync_project_and_build_start(
        self,
        project_id: str,
        project_name: str,
        build_id: str,
        requirement: str,
        detected_stack: Optional[str] = None,
        workspace_path: Optional[str] = None,
        estimated_duration: Optional[str] = None,
    ) -> None:
        """Persist project entity and new build record at pipeline onset."""
        try:
            self.projects.ensure_project(
                project_id=project_id,
                name=project_name,
                workspace_path=workspace_path,
                detected_stack=detected_stack,
                status="BUILDING",
            )
            self.builds.create_build(
                build_id=build_id,
                project_id=project_id,
                requirement=requirement,
                estimated_duration=estimated_duration,
                status="RUNNING",
            )
            self.activity.record_activity(
                build_id=build_id,
                message=f"Build initialized: '{requirement}'",
                event_type="INIT",
                agent="Orchestrator",
                status="RUNNING",
            )
        except Exception as exc:
            logger.warning(f"Database sync failed during build start: {exc}")

    def sync_agent_run_start(
        self,
        build_id: str,
        agent_name: str,
        task_id: Optional[str] = None,
    ) -> Optional[str]:
        """Record agent execution commencement, returning run_id."""
        try:
            record = self.agents.create_agent_run(
                build_id=build_id,
                agent_name=agent_name,
                task_id=task_id,
                status="WORKING",
            )
            return record.get("run_id")
        except Exception as exc:
            logger.warning(f"Database sync failed during agent run start: {exc}")
            return None

    def sync_agent_run_finish(
        self,
        run_id: str,
        status: str = "SUCCESS",
        duration: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record agent execution completion."""
        try:
            self.agents.finish_agent_run(
                run_id=run_id,
                status=status,
                duration=duration,
                error_message=error_message,
            )
        except Exception as exc:
            logger.warning(f"Database sync failed during agent run finish: {exc}")

    def sync_activity(
        self,
        build_id: str,
        message: str,
        event_type: str = "PIPELINE",
        agent: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """Persist activity event without throwing."""
        try:
            self.activity.record_activity(
                build_id=build_id,
                message=message,
                event_type=event_type,
                agent=agent,
                status=status,
            )
        except Exception as exc:
            logger.warning(f"Database sync failed recording activity: {exc}")

    def sync_runtime_start(
        self,
        build_id: str,
        project_id: str,
        framework: Optional[str],
        pid: Optional[int],
        port: Optional[int],
        url: Optional[str],
    ) -> Optional[str]:
        """Record launched runtime process session."""
        try:
            session = self.runtimes.create_session(
                build_id=build_id,
                project_id=project_id,
                framework=framework,
                pid=pid,
                port=port,
                url=url,
                status="RUNNING",
                health_status="HEALTHY",
            )
            return session.get("runtime_id")
        except Exception as exc:
            logger.warning(f"Database sync failed recording runtime start: {exc}")
            return None

    def sync_runtime_stop(self, runtime_id: str, status: str = "STOPPED") -> None:
        """Record runtime process termination."""
        try:
            self.runtimes.close_session(runtime_id=runtime_id, status=status)
        except Exception as exc:
            logger.warning(f"Database sync failed recording runtime stop: {exc}")

    def sync_verification_gate(
        self,
        build_id: str,
        gate_name: str,
        status: str,
        message: Optional[str] = None,
    ) -> None:
        """Record outcome of verification gate."""
        try:
            self.verification.record_gate_result(
                build_id=build_id,
                gate_name=gate_name,
                status=status,
                message=message,
            )
        except Exception as exc:
            logger.warning(f"Database sync failed recording verification: {exc}")

    def sync_build_finish(
        self,
        build_id: str,
        project_id: str,
        status: str,
        duration: Optional[float] = None,
        final_result: Optional[str] = None,
        failure_reason: Optional[str] = None,
        detected_stack: Optional[str] = None,
    ) -> None:
        """Mark build and project records with final outcome metrics."""
        try:
            self.builds.finish_build(
                build_id=build_id,
                status=status,
                duration=duration,
                final_result=final_result,
                failure_reason=failure_reason,
            )
            self.projects.update_project_status(
                project_id=project_id,
                status=status,
                detected_stack=detected_stack,
            )
            self.activity.record_activity(
                build_id=build_id,
                message=f"Build finished with status: {status}",
                event_type="COMPLETE" if status == "COMPLETED" else "FAILED",
                agent="Orchestrator",
                status=status,
            )
        except Exception as exc:
            logger.warning(f"Database sync failed during build finish: {exc}")

    def sync_build_interrupted(
        self,
        build_id: str,
        project_id: str,
        reason: str = "Build interrupted unexpectedly (e.g. process termination or server restart)",
    ) -> None:
        """Mark build and project records as INTERRUPTED."""
        try:
            self.builds.mark_interrupted(build_id=build_id, reason=reason)
            self.projects.update_project_status(project_id=project_id, status="INTERRUPTED")
            self.activity.record_activity(
                build_id=build_id,
                message=f"Build interrupted: {reason}",
                event_type="INTERRUPTED",
                agent="Orchestrator",
                status="INTERRUPTED",
            )
        except Exception as exc:
            logger.warning(f"Database sync failed during build interruption: {exc}")



def get_database_manager(db_path: Optional[Path] = None) -> DatabaseManager:
    """Return shared singleton DatabaseManager instance."""
    global _global_db_manager
    if _global_db_manager is None or (db_path and _global_db_manager.db_path != Path(db_path).resolve()):
        _global_db_manager = DatabaseManager(db_path)
    return _global_db_manager
