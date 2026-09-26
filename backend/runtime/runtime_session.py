"""Runtime Session and Process Lifecycle Management for SPIDY.

Provides isolated, observable RuntimeSession abstraction representing an active or
previous generated project process, its PID, ports, stdout/stderr, and verification states.
"""

from dataclasses import dataclass, field
import os
import re
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Set
import uuid

# Ports reserved for SPIDY Control Server / Streamlit. NEVER assign or treat as project ports.
SPIDY_CONTROL_PORTS: Set[int] = {8500, 8501, 8502}
NOVA_CONTROL_PORTS = SPIDY_CONTROL_PORTS  # Backward compatibility alias


@dataclass
class RuntimeSession:
    """Represents a dedicated execution session for a generated project."""

    project_id: str = "default_project"
    project_name: str = "SPIDY Project"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    command: List[str] = field(default_factory=list)
    cwd: str = ""
    framework: str = "General Application"
    host: str = "localhost"
    port: Optional[int] = None
    url: Optional[str] = None
    status: str = "NOT_STARTED"
    # Lifecycle states:
    # NOT_STARTED -> STARTING -> PROCESS_STARTED -> PORT_DETECTED ->
    # SERVER_READY -> HTTP_RESPONSIVE -> APPLICATION_VERIFIED -> RUNNING
    # Or: RECOVERING, FAILED, STOPPED

    startup_time: Optional[float] = None
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    verification_steps: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    is_app_verified: bool = False
    occupied_ports_seen: List[int] = field(default_factory=list)

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_stdout(self, line: str) -> None:
        with self._lock:
            self.stdout_lines.append(line)
            if len(self.stdout_lines) > 600:
                self.stdout_lines.pop(0)
            self._inspect_line(line)

    def add_stderr(self, line: str) -> None:
        with self._lock:
            self.stderr_lines.append(line)
            if len(self.stderr_lines) > 600:
                self.stderr_lines.pop(0)
            self._inspect_line(line)

    def _inspect_line(self, line: str) -> None:
        """Parse real-time stdout/stderr lines to capture port transitions and final URLs."""
        clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", line).strip()

        # 1. Detect port in-use notice (e.g. "Port 5173 is in use, trying another one...")
        occupied_match = re.search(r"Port\s+(\d+)\s+is in use", clean, re.IGNORECASE)
        if occupied_match:
            occ_port = int(occupied_match.group(1))
            if occ_port not in self.occupied_ports_seen:
                self.occupied_ports_seen.append(occ_port)
            if self.port == occ_port:
                self.port = None
                self.url = None
            return

        # 2. Match URLs from dev servers (Vite, Next, React Scripts, Webpack, etc.)
        patterns = [
            r"Local:\s+https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d+)",
            r"Network:\s+https?://[a-zA-Z0-9_.-]+:(\d+)",
            r"(?:listening|running|serving|ready|started)\s+(?:on|at)\s+(?:https?://)?(?:[a-zA-Z0-9_.-]+:)?(\d+)",
            r"(?:listening|running|serving|ready)\s+(?:on\s+)?port\s+(\d+)",
            r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d+)",
        ]

        for pat in patterns:
            matches = re.findall(pat, clean, re.IGNORECASE)
            for m in matches:
                try:
                    p = int(m)
                    # Filter out ports in NOVA control range (8500-8502) or invalid / in-use port numbers
                    if 1024 <= p <= 65535 and p not in NOVA_CONTROL_PORTS and p not in self.occupied_ports_seen:
                        self.port = p
                        self.url = f"http://localhost:{p}"
                        if self.status in ("NOT_STARTED", "STARTING", "PROCESS_STARTED"):
                            self.status = "PORT_DETECTED"
                        return
                except Exception:
                    pass

    def is_alive(self) -> bool:
        """Check if process is currently executing."""
        if not self.process:
            return False
        ret = self.process.poll()
        alive = ret is None
        if not alive and self.status in ("RUNNING", "PROCESS_STARTED", "STARTING", "PORT_DETECTED"):
            self.status = "FAILED" if self.process.returncode != 0 else "STOPPED"
        return alive

    def terminate(self) -> None:
        """Terminate the process and all of its child processes cleanly."""
        with self._lock:
            if self.process:
                pid = self.process.pid
                try:
                    if sys.platform == "win32":
                        # Windows taskkill with /T (tree kill) and /F (force) ensures child node.exe processes die
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            timeout=5,
                        )
                    else:
                        self.process.terminate()
                        self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
                self.process = None

            self.status = "STOPPED"
            self.is_app_verified = False

    def get_logs_text(self) -> str:
        """Return combined chronological logs."""
        with self._lock:
            all_lines = []
            for l in self.stdout_lines:
                all_lines.append(f"[STDOUT] {l}")
            for l in self.stderr_lines:
                all_lines.append(f"[STDERR] {l}")
            return "\n".join(all_lines)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "pid": self.pid,
            "command": " ".join(self.command),
            "cwd": self.cwd,
            "framework": self.framework,
            "port": self.port,
            "url": self.url,
            "status": self.status,
            "is_app_verified": self.is_app_verified,
            "verification_steps": list(self.verification_steps),
        }
