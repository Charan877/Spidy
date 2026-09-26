"""SQLite Database Schema and Version Management for SPIDY.

Defines tables, relationships, indexes, and idempotent schema migrations
for projects, builds, agent runs, activities, runtime sessions, and verification results.
"""

import logging
import sqlite3
from typing import Tuple

logger = logging.getLogger("spidy.database.schema")

CURRENT_SCHEMA_VERSION = 2

SCHEMA_V1_STATEMENTS = [
    # Schema version tracking
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 1. PROJECTS: Distinct software engineering projects
    """
    CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        workspace_path TEXT,
        detected_stack TEXT,
        status TEXT NOT NULL DEFAULT 'IDLE',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """,

    # 2. BUILDS: Execution lifecycle instances belonging to a project
    """
    CREATE TABLE IF NOT EXISTS builds (
        build_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        requirement TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'RUNNING',
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        duration REAL,
        estimated_duration TEXT,
        final_result TEXT,
        failure_reason TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    """,

    # 3. AGENT RUNS: Discrete execution records per agent per build
    """
    CREATE TABLE IF NOT EXISTS agent_runs (
        run_id TEXT PRIMARY KEY,
        build_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        task_id TEXT,
        status TEXT NOT NULL,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        duration REAL,
        error_message TEXT,
        FOREIGN KEY (build_id) REFERENCES builds(build_id) ON DELETE CASCADE
    );
    """,

    # 4. ACTIVITY: Granular timeline events and audit log
    """
    CREATE TABLE IF NOT EXISTS activity (
        activity_id TEXT PRIMARY KEY,
        build_id TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        agent TEXT,
        message TEXT NOT NULL,
        status TEXT,
        FOREIGN KEY (build_id) REFERENCES builds(build_id) ON DELETE CASCADE
    );
    """,

    # 5. RUNTIME SESSIONS: Isolated execution runtimes and process monitoring
    """
    CREATE TABLE IF NOT EXISTS runtime_sessions (
        runtime_id TEXT PRIMARY KEY,
        build_id TEXT NOT NULL,
        project_id TEXT NOT NULL,
        framework TEXT,
        pid INTEGER,
        port INTEGER,
        url TEXT,
        status TEXT NOT NULL,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        stopped_at TEXT,
        health_status TEXT,
        FOREIGN KEY (build_id) REFERENCES builds(build_id) ON DELETE CASCADE,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    """,

    # 6. VERIFICATION: Deterministic six-gate validation matrix records
    """
    CREATE TABLE IF NOT EXISTS verification (
        verification_id TEXT PRIMARY KEY,
        build_id TEXT NOT NULL,
        gate_name TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (build_id) REFERENCES builds(build_id) ON DELETE CASCADE
    );
    """,

    # Performance indexes for frequent queries
    "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);",
    "CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_builds_project_id ON builds(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_builds_status ON builds(status);",
    "CREATE INDEX IF NOT EXISTS idx_builds_started_at ON builds(started_at);",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_build_id ON agent_runs(build_id);",
    "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_name);",
    "CREATE INDEX IF NOT EXISTS idx_activity_build_id ON activity(build_id);",
    "CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_runtime_sessions_build_id ON runtime_sessions(build_id);",
    "CREATE INDEX IF NOT EXISTS idx_runtime_sessions_project_id ON runtime_sessions(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_runtime_sessions_status ON runtime_sessions(status);",
    "CREATE INDEX IF NOT EXISTS idx_verification_build_id ON verification(build_id);",
    "CREATE INDEX IF NOT EXISTS idx_verification_gate ON verification(gate_name);",
]

SCHEMA_V2_STATEMENTS = [
    # 7. MESSAGES: Conversational interaction history per project
    """
    CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        build_id TEXT,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        classification TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_project_id ON messages(project_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);",
]


def get_current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the currently applied schema version from the database, or 0 if uninitialized."""
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
        )
        if not cursor.fetchone():
            return 0
        cursor = conn.execute("SELECT MAX(version) FROM schema_version;")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else 0
    except sqlite3.Error as exc:
        logger.error(f"Error querying schema version: {exc}")
        return 0


def initialize_schema(conn: sqlite3.Connection) -> Tuple[bool, int]:
    """Idempotently initialize and upgrade SQLite database schema.
    
    Returns (was_upgraded, active_version).
    """
    version = get_current_schema_version(conn)
    if version >= CURRENT_SCHEMA_VERSION:
        return False, version

    logger.info(f"Applying schema migration from version {version} to {CURRENT_SCHEMA_VERSION}...")
    cursor = conn.cursor()

    if version < 1:
        for stmt in SCHEMA_V1_STATEMENTS:
            cursor.execute(stmt)
        cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (1);")
        conn.commit()
        logger.info("Schema version 1 initialized successfully.")

    if version < 2:
        for stmt in SCHEMA_V2_STATEMENTS:
            cursor.execute(stmt)
            
        # Add new columns to projects if they don't exist yet
        try:
            cursor.execute("SELECT architecture_summary FROM projects LIMIT 1;")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE projects ADD COLUMN architecture_summary TEXT;")

        try:
            cursor.execute("SELECT contract_json FROM projects LIMIT 1;")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE projects ADD COLUMN contract_json TEXT;")

        try:
            cursor.execute("SELECT conversation_id FROM projects LIMIT 1;")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE projects ADD COLUMN conversation_id TEXT;")

        cursor.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (2);")
        conn.commit()
        logger.info("Schema version 2 applied successfully (messages and conversation fields).")

    return True, CURRENT_SCHEMA_VERSION
