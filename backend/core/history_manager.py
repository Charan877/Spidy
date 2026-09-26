"""Lightweight project and build history manager for SPIDY.

Persists completed and active project metadata to a local JSON store
without bloating ProjectState. Superseded primarily by backend.database (SQLite),
retained for local snapshot caching.
"""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import time
from typing import Dict, List, Optional


@dataclass
class ProjectRecord:
    project_id: str
    project_name: str
    goal: str
    tech_stack: str
    status: str  # "COMPLETED", "FAILED", "IN_PROGRESS"
    actual_duration_str: str
    actual_duration_seconds: float
    estimate_range: str
    timestamp: str
    file_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectRecord":
        return cls(**data)


class HistoryManager:
    """Manages reading and writing project build history."""

    def __init__(self, history_file: Optional[str] = None):
        if history_file:
            self.history_file = Path(history_file)
        elif Path(".spidy_history.json").exists():
            self.history_file = Path(".spidy_history.json")
        elif Path(".nova_history.json").exists():
            self.history_file = Path(".nova_history.json")
        else:
            self.history_file = Path(".spidy_history.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.history_file.exists():
            default_history = [
                {
                    "project_id": "messi-legacy-01",
                    "project_name": "Lionel Messi: The Legacy",
                    "goal": "Interactive 3D narrative journey through Lionel Messi's career with WebGL stadium & audio",
                    "tech_stack": "React / Vite / Three.js",
                    "status": "COMPLETED",
                    "actual_duration_str": "9m 14s",
                    "actual_duration_seconds": 554.0,
                    "estimate_range": "~8–12 MIN",
                    "timestamp": "2026-09-22 15:50",
                    "file_count": 12,
                }
            ]
            try:
                self.history_file.write_text(json.dumps(default_history, indent=2), encoding="utf-8")
            except Exception:
                pass

    def get_recent_projects(self, limit: int = 10) -> List[ProjectRecord]:
        try:
            if not self.history_file.exists():
                return []
            content = self.history_file.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            records = [ProjectRecord.from_dict(item) for item in data]
            records.sort(key=lambda r: r.timestamp, reverse=True)
            return records[:limit]
        except Exception:
            return []

    def get_history(self, limit: int = 20) -> List[dict]:
        records = self.get_recent_projects(limit)
        return [r.to_dict() for r in records]

    def record_project(
        self,
        project_name: str,
        goal: str,
        tech_stack: str,
        status: str,
        duration_seconds: float,
        duration_str: str,
        estimate_range: str,
        file_count: int = 0,
    ) -> None:
        records = self.get_recent_projects(50)
        project_id = f"proj-{int(time.time())}"
        ts = time.strftime("%Y-%m-%d %H:%M")
        
        # Check if updating an existing record with the same name
        existing = next((r for r in records if r.project_name == project_name), None)
        if existing:
            existing.status = status
            existing.actual_duration_seconds = duration_seconds
            existing.actual_duration_str = duration_str
            existing.timestamp = ts
            existing.file_count = file_count
        else:
            new_record = ProjectRecord(
                project_id=project_id,
                project_name=project_name,
                goal=goal,
                tech_stack=tech_stack,
                status=status,
                actual_duration_str=duration_str,
                actual_duration_seconds=duration_seconds,
                estimate_range=estimate_range,
                timestamp=ts,
                file_count=file_count,
            )
            records.insert(0, new_record)

        try:
            self.history_file.write_text(
                json.dumps([r.to_dict() for r in records[:20]], indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
