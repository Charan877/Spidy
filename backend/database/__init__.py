"""SPIDY Database Layer.

Provides local SQLite persistence for projects, builds, agent runs,
activities, runtime sessions, and verification matrices.
"""

from backend.database.connection import DatabaseConnectionFactory, get_default_db_path
from backend.database.database_manager import DatabaseManager, get_database_manager
from backend.database.schema import CURRENT_SCHEMA_VERSION, initialize_schema

__all__ = [
    "DatabaseConnectionFactory",
    "DatabaseManager",
    "get_database_manager",
    "get_default_db_path",
    "initialize_schema",
    "CURRENT_SCHEMA_VERSION",
]
