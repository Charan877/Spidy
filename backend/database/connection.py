"""SQLite Database Connection Manager for SPIDY.

Provides robust, thread-safe SQLite connection management with automatic
directory provisioning, WAL mode, foreign key enforcement, and configurable timeouts.
"""

from contextlib import contextmanager
import logging
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Generator, Optional

logger = logging.getLogger("spidy.database.connection")

# Default database location: <project_root>/data/spidy.db
DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "spidy.db"


def current_utc_iso() -> str:
    """Return timezone-aware UTC ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def get_default_db_path() -> Path:
    """Return configured database path from environment or default location."""
    env_path = os.getenv("SPIDY_DB_PATH")
    if env_path:
        return Path(env_path).resolve()
    return DEFAULT_DB_PATH


class DatabaseConnectionFactory:
    """Manages SQLite connection lifecycle and configuration."""

    def __init__(self, db_path: Optional[Path] = None, timeout: float = 10.0):
        self.db_path = Path(db_path).resolve() if db_path else get_default_db_path()
        self.timeout = timeout
        self.ensure_directory()

    def ensure_directory(self) -> None:
        """Create parent directory for the SQLite database if missing."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error(f"Failed to create database directory {self.db_path.parent}: {exc}")
            raise

    def create_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        self.ensure_directory()
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=self.timeout,
                check_same_thread=False,
            )
            # Enable dictionary-like row access
            conn.row_factory = sqlite3.Row

            # Apply robust SQLite pragmas
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 5000;")

            # In-memory databases do not support WAL mode
            if str(self.db_path) != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA synchronous = NORMAL;")

            return conn
        except sqlite3.Error as exc:
            logger.error(f"Failed to establish SQLite connection to {self.db_path}: {exc}")
            raise

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an active SQLite connection with automatic commit/rollback."""
        conn = self.create_connection()
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except sqlite3.Error:
                pass
            logger.error(f"Transaction failed, rolled back: {exc}")
            raise
        finally:
            try:
                conn.close()
            except sqlite3.Error:
                pass
