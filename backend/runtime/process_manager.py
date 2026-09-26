"""Process Manager for SPIDY.

Handles non-blocking subprocess management, dedicated RuntimeSessions,
continuous stdout/stderr stream parsing, process identity verification,
listening socket ownership tracking, dynamic port detection, and clean process termination.
"""

import os
import re
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Set
from backend.runtime.runtime_session import RuntimeSession, NOVA_CONTROL_PORTS


def get_process_tree_pids(root_pid: int) -> Set[int]:
    """Return all PIDs belonging to the process tree rooted at root_pid."""
    if not root_pid:
        return set()
    tree = {root_pid}
    if sys.platform == "win32":
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId",
            ]
            out = subprocess.check_output(
                cmd,
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=4,
            )
            parent_map: Dict[int, List[int]] = {}
            for line in out.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    pid, ppid = int(parts[0]), int(parts[1])
                    parent_map.setdefault(ppid, []).append(pid)

            # BFS to gather all descendant PIDs
            queue = [root_pid]
            while queue:
                curr = queue.pop(0)
                for child in parent_map.get(curr, []):
                    if child not in tree:
                        tree.add(child)
                        queue.append(child)
        except Exception:
            pass
    return tree


def get_port_owner_pid(port: int) -> Optional[int]:
    """Inspect which PID is currently listening on the given TCP port."""
    if not port:
        return None
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=3,
            )
            target = f":{port}"
            for line in out.splitlines():
                line = line.strip()
                if "LISTENING" in line and target in line:
                    parts = line.split()
                    if len(parts) >= 5 and parts[-1].isdigit():
                        if parts[1].endswith(target):
                            return int(parts[-1])
    except Exception:
        pass
    return None


def verify_process_port_ownership(session: RuntimeSession) -> bool:
    """Verify that the port assigned to the session is actually owned by the session's process tree."""
    if not session.port:
        return False
    if not session.pid:
        return True

    owner_pid = get_port_owner_pid(session.port)
    if not owner_pid:
        # Port might still be in startup or not bound to socket yet
        return True

    tree = get_process_tree_pids(session.pid)
    return owner_pid in tree


def discover_ports_by_pid(pid: int) -> List[int]:
    """Inspect listening TCP sockets for a process PID and all of its child processes."""
    if not pid:
        return []
    ports = []
    try:
        target_pids = get_process_tree_pids(pid)
        target_pid_strs = {str(p) for p in target_pids}

        if sys.platform == "win32":
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=3,
            )
            for line in out.splitlines():
                line = line.strip()
                if "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5 and parts[-1] in target_pid_strs:
                        match = re.search(r":(\d+)$", parts[1])
                        if match:
                            p = int(match.group(1))
                            if p not in NOVA_CONTROL_PORTS and 1024 <= p <= 65535:
                                if p not in ports:
                                    ports.append(p)
    except Exception:
        pass
    return ports


class ProcessManager:
    """Coordinates isolated RuntimeSessions for generated software projects."""

    def __init__(self):
        self.active_session: Optional[RuntimeSession] = None
        self.active_sessions: List[RuntimeSession] = []
        self.sessions_history: List[RuntimeSession] = []
        self._lock = threading.Lock()

    def start_session(
        self,
        command: List[str],
        cwd: str,
        project_id: str = "default_project",
        project_name: str = "SPIDY Project",
        framework: str = "General Application",
        explicit_port: Optional[int] = None,
        stop_existing: bool = True,
    ) -> RuntimeSession:
        """Start a new project process in a dedicated RuntimeSession."""
        if stop_existing:
            self.stop_all()

        session = RuntimeSession(
            project_id=project_id,
            project_name=project_name,
            command=command,
            cwd=cwd,
            framework=framework,
            port=explicit_port,
            url=f"http://localhost:{explicit_port}" if explicit_port else None,
            status="STARTING",
            startup_time=time.time(),
        )

        cmd_str = " ".join(command)
        session.add_stdout(f"Starting process: {cmd_str}")

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=creationflags,
            )

            session.process = proc
            session.pid = proc.pid
            session.status = "PROCESS_STARTED"
            session.verification_steps.append("Process started")

            # Background stream reader threads
            threading.Thread(target=self._stream_reader, args=(proc.stdout, session, "out"), daemon=True).start()
            threading.Thread(target=self._stream_reader, args=(proc.stderr, session, "err"), daemon=True).start()

            with self._lock:
                self.active_session = session
                if session not in self.active_sessions:
                    self.active_sessions.append(session)
                self.sessions_history.append(session)

            return session

        except Exception as exc:
            session.status = "FAILED"
            session.error_message = str(exc)
            session.add_stderr(f"Failed to spawn process: {exc}")
            with self._lock:
                self.active_session = session
                if session not in self.active_sessions:
                    self.active_sessions.append(session)
                self.sessions_history.append(session)
            return session

    def _stream_reader(self, stream, session: RuntimeSession, stream_type: str) -> None:
        """Continuous reader sending lines to session for port parsing and log tracking."""
        if not stream:
            return
        try:
            for line in iter(stream.readline, ""):
                if line:
                    clean = line.strip()
                    if stream_type == "out":
                        session.add_stdout(clean)
                    else:
                        session.add_stderr(clean)
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def wait_for_port(self, session: RuntimeSession, timeout: float = 12.0) -> Optional[int]:
        """Wait for server to report its port via stdout or verify that a socket is genuinely listening."""
        start_t = time.time()
        while time.time() - start_t < timeout:
            if not session.is_alive():
                exit_code = session.process.poll() if session.process else -1
                session.add_stderr(f"Process terminated prematurely (exit code {exit_code}).")
                return None

            # 1. If dev server logged port via stdout (session.port is populated)
            if session.port:
                owner_pid = get_port_owner_pid(session.port)
                if owner_pid:
                    tree = get_process_tree_pids(session.pid) if session.pid else set()
                    if not tree or owner_pid in tree:
                        session.status = "PORT_DETECTED"
                        return session.port
                    else:
                        # Collision: another unrelated process owns this port!
                        session.add_stderr(
                            f"Port collision: port {session.port} is owned by PID {owner_pid} (not in project tree)."
                        )
                        session.occupied_ports_seen.append(session.port)
                        session.port = None
                        session.url = None
                else:
                    # In dev servers (Vite/Streamlit) or mock sessions, return logged port once detected in stdout
                    if session.port:
                        session.status = "PORT_DETECTED"
                        return session.port

            # 2. Check if process tree is listening on ANY socket
            if session.pid:
                detected = discover_ports_by_pid(session.pid)
                if detected:
                    session.port = detected[0]
                    session.url = f"http://localhost:{detected[0]}"
                    session.status = "PORT_DETECTED"
                    return detected[0]

            time.sleep(0.15)

        return None

    def stop_all(self) -> None:
        """Terminate active sessions and any stale child processes."""
        with self._lock:
            for s in self.active_sessions:
                if s and s.is_alive():
                    s.terminate()
            if self.active_session and self.active_session.is_alive():
                self.active_session.terminate()
            self.active_sessions.clear()
            self.active_session = None

    # Backward-compatible accessors for existing callers
    @property
    def port(self) -> Optional[int]:
        return self.active_session.port if self.active_session else None

    @property
    def url(self) -> Optional[str]:
        return self.active_session.url if self.active_session else None

    @property
    def status(self) -> str:
        return self.active_session.status if self.active_session else "NOT_STARTED"

    def is_alive(self) -> bool:
        if self.active_session and self.active_session.is_alive():
            return True
        return any(s.is_alive() for s in self.active_sessions)

    def get_logs_text(self) -> str:
        with self._lock:
            if not self.active_sessions and not self.active_session:
                return ""
            if len(self.active_sessions) <= 1:
                return self.active_session.get_logs_text() if self.active_session else ""
            logs = []
            for s in self.active_sessions:
                prefix = f"=== [{s.framework} : PID {s.pid or 'N/A'}] ==="
                logs.append(f"{prefix}\n{s.get_logs_text()}")
            return "\n\n".join(logs)

    def stop(self) -> None:
        self.stop_all()

    def start(self, command: List[str], cwd: str, port: Optional[int] = None, url: Optional[str] = None) -> bool:
        """Backward-compatible start wrapper."""
        session = self.start_session(command=command, cwd=cwd, explicit_port=port)
        time.sleep(0.8)
        return session.is_alive()
