"""Workspace Manager for SPIDY.

Handles multi-file read/write operations strictly scoped inside the workspace directory.
Supports project-scoped isolation (workspace/<project_id>/) to prevent cross-project pollution.
Prevents file access escaping the workspace root.
"""

import os
from pathlib import Path
import re
from typing import Dict, List, Optional


class WorkspaceManager:
    """Manages files within the project workspace safely with per-project isolation."""

    def __init__(self, workspace_dir: Optional[str] = None, project_id: Optional[str] = None):
        base = Path(__file__).resolve().parent.parent.parent / "workspace"
        if workspace_dir:
            self.root = Path(workspace_dir).resolve()
        elif project_id:
            safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", project_id).strip("_") or "default"
            self.root = (base / safe_id).resolve()
        else:
            self.root = base.resolve()
        self.ensure_workspace()

    @classmethod
    def for_project(cls, project_id: str, base_dir: Optional[str] = None) -> "WorkspaceManager":
        """Instantiate a WorkspaceManager isolated strictly to a specific project_id."""
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", project_id).strip("_") or "default"
        base = Path(base_dir).resolve() if base_dir else (Path(__file__).resolve().parent.parent.parent / "workspace")
        return cls(workspace_dir=str(base / safe_id))

    def ensure_workspace(self) -> None:
        """Create the workspace root if it does not exist."""
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Ensure the target file path stays strictly inside self.root."""
        # Normalize and remove leading slashes/backslashes
        cleaned = relative_path.lstrip("/\\")
        target = (self.root / cleaned).resolve()
        try:
            target.relative_to(self.root)
        except ValueError:
            raise PermissionError(
                f"Security Violation: Target path '{relative_path}' escapes workspace '{self.root}'"
            )
        return target

    def write_file(self, relative_path: str, content: str) -> str:
        """Write content to a file inside the workspace, creating parent dirs if needed."""
        target = self._resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def read_file(self, relative_path: str) -> str:
        """Read text content of a file inside the workspace."""
        target = self._resolve_safe_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"File '{relative_path}' not found in workspace.")
        return target.read_text(encoding="utf-8")

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists safely within the workspace."""
        try:
            return self._resolve_safe_path(relative_path).exists()
        except Exception:
            return False

    IGNORED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", ".pytest_cache", ".turbo", ".next"}

    def list_files(self) -> List[str]:
        """Return a sorted list of relative paths for all files in the workspace, skipping dependencies."""
        if not self.root.exists():
            return []
        results = []
        for path in self.root.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                # Exclude paths within ignored directories like node_modules
                parts = set(path.relative_to(self.root).parts)
                if not parts.intersection(self.IGNORED_DIRS):
                    rel = path.relative_to(self.root).as_posix()
                    results.append(rel)
        return sorted(results)

    def load_all_files(self) -> Dict[str, str]:
        """Read and return a dictionary of {relative_path: content} for all workspace files."""
        files = {}
        for rel_path in self.list_files():
            try:
                files[rel_path] = self.read_file(rel_path)
            except Exception:
                pass
        return files

    def clear_workspace(self) -> None:
        """Safely delete all files inside the workspace directory."""
        if not self.root.exists():
            return
        for item in self.root.glob("*"):
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil

                shutil.rmtree(item, ignore_errors=True)

    def clean(self) -> None:
        """Alias for clear_workspace."""
        self.clear_workspace()

