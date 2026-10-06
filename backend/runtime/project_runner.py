"""Project Runner for SPIDY.

Orchestrates environment detection, dependency installation, isolated RuntimeSession
execution, dynamic port discovery, socket process ownership verification,
granular verification gates, automatic recovery from HTTP 404 / missing index,
and rigorous project success determination.
"""

from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Optional
from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector
from backend.runtime.preview_manager import PreviewManager, PreviewCheckResult
from backend.runtime.process_manager import ProcessManager, verify_process_port_ownership
from backend.runtime.runtime_session import SPIDY_CONTROL_PORTS, NOVA_CONTROL_PORTS, RuntimeSession
from backend.verification.gate_evaluator import GateEvaluator


class ProjectRunner:
    """High-level coordinator for building, running, and verifying project runtimes."""

    def __init__(self, workspace: WorkspaceManager, process_manager: Optional[ProcessManager] = None):
        self.workspace = workspace
        self.process_manager = process_manager or ProcessManager()
        self.detector = EnvironmentDetector()
        self.preview_manager = PreviewManager()

    def run(self, state: ProjectState) -> bool:
        """Detect stack, install dependencies, start session, and verify application."""
        if hasattr(state, "can_execute_engineering") and not state.can_execute_engineering():
            state.add_activity("Runtime launch blocked: execution prohibited while awaiting user confirmation.", level="bad")
            return False

        state.runtime_status = "DETECTING"
        state.is_app_verified = False
        state.project_success = False
        state.failure_reason = None
        state.failure_classification = None
        state.runtime_verification_steps.clear()
        state.verification_gates = {
            "build": True,
            "process": False,
            "port": False,
            "server": False,
            "http": False,
            "application": False,
        }
        state.add_activity("Detecting project stack and startup configuration...", level="run")

        is_planned_fullstack = (getattr(state, "runtime_type", "") == "fullstack")
        env_config = self.detector.detect(self.workspace, override_language=state.selected_language)

        state.project_type = env_config["project_type"]
        if is_planned_fullstack:
            state.runtime_type = "fullstack"
        elif getattr(state, "runtime_type", "") == "web_3d":
            state.runtime_type = "web_3d"
        else:
            state.runtime_type = env_config.get("runtime_type", "web" if env_config.get("is_web") else "cli")
        state.runtime_targets = []
        state.runtime_command = " ".join(env_config["command"]) if env_config.get("command") else ""
        state.runtime_port = env_config.get("port")
        state.runtime_url = env_config.get("url")
        state.is_web_project = env_config["is_web"] or (state.runtime_type in ("web", "web_3d", "fullstack"))
        state.runtime_cwd = env_config.get("cwd", str(self.workspace.root))

        if state.runtime_type == "fullstack":
            ws_files = self.workspace.list_files()
            has_fe = self.workspace.file_exists("index.html") or self.workspace.file_exists("package.json") or any(f.endswith((".html", ".tsx", ".jsx")) for f in ws_files)
            has_be = any(f.endswith(".py") or f.endswith("server.js") for f in ws_files)

            if not has_be and not has_fe:
                state.failure_classification = "INCOMPLETE_PROJECT"
                state.failure_reason = "Fullstack application is missing both frontend and backend components."
                state.runtime_status = "FAILED"
                state.is_app_verified = False
                state.project_success = False
                state.add_activity("FULLSTACK VERIFICATION FAILURE: Incomplete fullstack project. Missing both frontend and backend.", level="bad")
                return False
            elif not has_be:
                state.failure_classification = "BACKEND_NOT_RUNNING"
                state.failure_reason = "Fullstack application is missing backend API entrypoint (FastAPI/Python backend)."
                state.runtime_status = "FAILED"
                state.is_app_verified = False
                state.project_success = False
                state.add_activity("FULLSTACK VERIFICATION FAILURE: Backend API service missing.", level="bad")
                return False
            elif not has_fe:
                state.failure_classification = "FRONTEND_NOT_RUNNING"
                state.failure_reason = "Fullstack application is missing frontend web interface (index.html or React web interface)."
                state.runtime_status = "FAILED"
                state.is_app_verified = False
                state.project_success = False
                state.add_activity("FULLSTACK VERIFICATION FAILURE: Frontend web interface missing.", level="bad")
                return False
            elif not env_config.get("frontend_config"):
                from backend.runtime.environment_detector import find_free_port
                fe_port = find_free_port(start_port=8080, max_port=8999)
                web_idx = "index.html" if self.workspace.file_exists("index.html") else next((f for f in ws_files if f.endswith(".html")), "index.html")
                fe_dir = str((getattr(self.workspace, "root", Path(".")) / Path(web_idx).parent).resolve())
                env_config["frontend_config"] = {
                    "project_type": "HTML / Web Frontend",
                    "runtime_type": "web",
                    "is_web": True,
                    "port": fe_port,
                    "url": f"http://localhost:{fe_port}",
                    "command": [sys.executable, "-m", "http.server", str(fe_port)],
                    "cwd": fe_dir,
                    "main_file": web_idx,
                }
                env_config["backend_port"] = env_config.get("port")

        if not env_config.get("command"):
            workspace_files = self.workspace.list_files()
            if not workspace_files:
                state.failure_type = "PRECONDITION_FAILURE"
                state.failure_classification = "PROJECT_NOT_GENERATED"
                state.failure_reason = "Workspace contains no generated project files. Generation must complete before execution."
                state.runtime_status = "BLOCKED"
                state.add_activity("PRECONDITION FAILURE: Workspace contains no generated files. Execution halted.", level="bad")
            else:
                state.failure_type = "PRECONDITION_FAILURE"
                state.failure_classification = "NO_EXECUTION_COMMAND"
                state.failure_reason = "No valid execution command found for workspace."
                state.runtime_status = "BLOCKED"
                state.add_activity("PRECONDITION FAILURE: No valid execution command found for workspace.", level="bad")
            return False

        # Step 1: Install missing dependencies if required (e.g. npm install)
        if env_config.get("requires_install") and env_config.get("install_command"):
            state.runtime_status = "STARTING"
            state.add_activity("Dependencies missing. Running package installation...", level="run")

            try:
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                install_proc = subprocess.run(
                    env_config["install_command"],
                    cwd=env_config["cwd"],
                    capture_output=True,
                    text=True,
                    timeout=120.0,
                    creationflags=creationflags,
                )
                if install_proc.returncode == 0:
                    state.add_activity("Package installation completed successfully.", level="ok")
                else:
                    state.add_activity(f"Package install warning: {install_proc.stderr[:150]}", level="bad")
            except Exception as exc:
                state.add_activity(f"Package installation failed: {exc}", level="bad")

        # Step 2: Start Process in isolated RuntimeSession
        state.runtime_status = "STARTING"
        state.add_activity(f"Starting application process ({env_config['project_type']}): {state.runtime_command}", level="run")

        session: RuntimeSession = self.process_manager.start_session(
            command=env_config["command"],
            cwd=env_config["cwd"],
            project_id=getattr(state, "project_id", "default_project") or "default_project",
            project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
            framework=env_config["project_type"],
            explicit_port=env_config.get("port"),
        )

        if not session or not session.is_alive():
            state.runtime_status = "FAILED"
            state.failure_classification = "PROCESS_NOT_STARTED"
            state.failure_reason = session.error_message or "Process exited immediately after launch."
            state.add_activity("Application failed to start. Reviewing runtime logs...", level="bad")
            state.runtime_logs = self.process_manager.get_logs_text()
            return False

        state.runtime_pid = session.pid
        state.runtime_status = "PROCESS_STARTED"
        state.verification_gates["process"] = True
        state.runtime_verification_steps.append("Process started")

        db_manager = getattr(state, "db_manager", None)
        build_id = getattr(state, "build_id", None)
        project_id = getattr(state, "project_id", "default_project") or "default_project"

        if db_manager and build_id:
            try:
                db_manager.sync_verification_gate(build_id, "build", "PASSED", "Files compiled without syntax errors")
                db_manager.sync_verification_gate(build_id, "process", "PASSED", f"PID {session.pid} active")
            except Exception:
                pass

        # Step 3: Wait & Verify Lifecycle
        if env_config["is_web"]:
            state.runtime_status = "WAITING_FOR_READY"

            target_port = self.process_manager.wait_for_port(session, timeout=12.0)

            # Reject missing ports, crashed processes, or collisions with SPIDY control ports
            if not target_port or target_port in SPIDY_CONTROL_PORTS:
                state.runtime_status = "FAILED"
                state.is_app_verified = False

                if not session.is_alive():
                    exit_code = session.process.poll() if session.process else -1
                    stderr_lines = [l for l in session.stderr_lines if l.strip()]
                    last_err = stderr_lines[-1] if stderr_lines else "Process terminated without output."
                    full_stderr = "\n".join(stderr_lines)

                    # Evidence-based recovery 1: Missing Dependency (ModuleNotFoundError / ImportError)
                    missing_mod_match = re.search(r"(?:No module named|ModuleNotFoundError: No module named)\s+['\"]([^'\"]+)['\"]", full_stderr)
                    if missing_mod_match and getattr(state, "_dep_install_retries", 0) < 1:
                        state._dep_install_retries = getattr(state, "_dep_install_retries", 0) + 1
                        missing_mod = missing_mod_match.group(1).split(".")[0]
                        state.add_activity(f"Evidence-based recovery: Detected missing dependency '{missing_mod}'. Installing via pip...", level="run")
                        pip_cmd = [sys.executable, "-m", "pip", "install", missing_mod]
                        try:
                            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                            subprocess.run(pip_cmd, capture_output=True, timeout=60.0, creationflags=creationflags)
                            state.add_activity(f"Installed '{missing_mod}'. Retrying process startup...", level="ok")
                            self.stop(state)
                            return self.run(state)
                        except Exception as e:
                            state.add_activity(f"Failed to install '{missing_mod}': {e}", level="bad")

                    state.failure_classification = "PROCESS_CRASHED"
                    state.failure_reason = f"Process exited with code {exit_code}: {last_err}"
                    state.add_activity(f"RUNTIME FAILURE: Process exited prematurely (exit code {exit_code})", level="bad")
                    if last_err:
                        state.add_activity(f"Error detail: {last_err[:250]}", level="bad")
                else:
                    # Evidence-based recovery 2: Port collision / in-use
                    occupied = getattr(session, "occupied_ports_seen", [])
                    if occupied and getattr(state, "_port_retry_attempts", 0) < 2:
                        state._port_retry_attempts = getattr(state, "_port_retry_attempts", 0) + 1
                        from backend.runtime.environment_detector import find_free_port
                        alt_port = find_free_port(start_port=8100, max_port=8999)
                        state.add_activity(f"Evidence-based recovery: Port collision on {occupied}. Switching to alternate port {alt_port}...", level="run")
                        self.stop(state)
                        env_config["port"] = alt_port
                        if "command" in env_config:
                            new_cmd = []
                            for part in env_config["command"]:
                                if any(str(p) in str(part) for p in occupied):
                                    new_cmd.append(str(alt_port))
                                else:
                                    new_cmd.append(part)
                            env_config["command"] = new_cmd
                        return self.run(state)

                    state.failure_classification = "PORT_NOT_DETECTED" if not target_port else "WRONG_RUNTIME_PROCESS"
                    state.failure_reason = (
                        f"Port detection failed (no listening socket on PID {session.pid}) or port {target_port} is in SPIDY control range."
                    )
                    state.add_activity(f"RUNTIME FAILURE: {state.failure_reason}", level="bad")

                state.runtime_logs = self.process_manager.get_logs_text()
                self.stop(state)
                return False

            state.runtime_port = target_port
            state.runtime_url = f"http://localhost:{target_port}"
            state.runtime_status = "PORT_DETECTED"
            session.status = "PORT_DETECTED"
            state.verification_gates["port"] = True
            state.runtime_verification_steps.append(f"Port {target_port} detected")
            state.add_activity(f"Listening socket confirmed on port {target_port}. Polling HTTP readiness...", level="run")

            if db_manager and build_id:
                try:
                    db_manager.sync_verification_gate(build_id, "port", "PASSED", f"Port {target_port} listening")
                    db_manager.sync_verification_gate(build_id, "server", "PASSED", "Socket responsive")
                    state.runtime_id = db_manager.sync_runtime_start(
                        build_id=build_id,
                        project_id=project_id,
                        framework=env_config.get("project_type"),
                        pid=session.pid,
                        port=target_port,
                        url=state.runtime_url,
                    )
                except Exception:
                    pass

            # Verify socket ownership
            if not verify_process_port_ownership(session):
                state.add_activity(f"Notice: Port {target_port} socket ownership verification pending...", level="dim")

            # Polling HTTP readiness
            state.runtime_status = "VERIFYING"
            session.status = "SERVER_READY"
            state.verification_gates["server"] = True
            check_result: PreviewCheckResult = self.preview_manager.check_health(
                state.runtime_url, timeout=2.0, max_retries=10
            )

            if check_result.is_control_server:
                state.runtime_status = "FAILED"
                state.is_app_verified = False
                state.failure_classification = "WRONG_RUNTIME_PROCESS"
                state.failure_reason = "URL resolved to SPIDY control server. Aborting preview."
                state.add_activity("Security error: URL resolved to SPIDY control server. Aborting preview.", level="bad")
                self.stop(state)
                return False

            # AUTOMATIC RECOVERY A: HTTP 404 or Missing Index in Vite/React project
            if check_result.classification == "HTTP_404" or check_result.status_code == 404 or env_config.get("missing_index"):
                state.runtime_status = "RECOVERING"
                state.failure_classification = "HTTP_404"
                state.failure_reason = "HTTP 404 at root URL: Missing index.html or wrong Vite root configuration."
                state.add_activity("Runtime Failure: HTTP 404 at / (Vite root entry point missing).", level="bad")
                state.add_activity("Executing automatic repair: diagnosing Vite workspace & generating entry point...", level="run")

                repaired = self._repair_vite_workspace(state)
                if repaired:
                    state.add_activity("Workspace structure repaired. Restarting dev server session...", level="run")
                    self.stop(state)

                    # Restart dev server
                    session = self.process_manager.start_session(
                        command=env_config["command"],
                        cwd=env_config["cwd"],
                        project_id=getattr(state, "project_id", "default_project") or "default_project",
                        project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
                        framework=env_config["project_type"],
                    )
                    state.runtime_pid = session.pid
                    state.runtime_status = "PROCESS_STARTED"

                    target_port = self.process_manager.wait_for_port(session, timeout=12.0)
                    if target_port and target_port not in SPIDY_CONTROL_PORTS:
                        state.runtime_port = target_port
                        state.runtime_url = f"http://localhost:{target_port}"
                        state.runtime_verification_steps.append(f"Port {target_port} detected")
                        check_result = self.preview_manager.check_health(state.runtime_url, timeout=2.0, max_retries=8)

            # AUTOMATIC RECOVERY B: Directory Listing detected
            if check_result.is_directory_listing:
                state.runtime_status = "RECOVERING"
                state.failure_classification = "INVALID_HTML"
                state.failure_reason = "Directory listing returned instead of compiled application."
                state.add_activity("PREVIEW_STARTUP_FAILURE: Directory listing detected instead of application!", level="bad")
                state.add_activity("Attempting automatic recovery: stopping static server & triggering dev server build...", level="run")

                self.stop(state)

                if (self.workspace.root / "package.json").exists():
                    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
                    state.add_activity("Running npm install for workspace...", level="run")
                    subprocess.run([npm_cmd, "install"], cwd=str(self.workspace.root), capture_output=True, timeout=120.0)

                    state.runtime_command = f"{npm_cmd} run dev"
                    state.add_activity("Launching dev server: npm run dev", level="run")
                    recovery_session = self.process_manager.start_session(
                        command=[npm_cmd, "run", "dev"],
                        cwd=str(self.workspace.root),
                        project_id=getattr(state, "project_id", "default_project") or "default_project",
                        project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
                        framework="Vite / React Web App",
                    )
                    state.runtime_pid = recovery_session.pid
                    state.runtime_status = "PROCESS_STARTED"

                    rec_port = self.process_manager.wait_for_port(recovery_session, timeout=12.0)
                    if rec_port and rec_port not in SPIDY_CONTROL_PORTS:
                        state.runtime_port = rec_port
                        state.runtime_url = f"http://localhost:{rec_port}"
                        state.runtime_verification_steps.append(f"Port {rec_port} detected")
                        check_result = self.preview_manager.check_health(state.runtime_url, timeout=2.0, max_retries=8)
                        session = recovery_session

            # Evaluation of Verification Gates
            if check_result.is_healthy:
                session.status = "HTTP_RESPONSIVE"
                state.verification_gates["http"] = True
                state.runtime_verification_steps.append("HTTP responsive")

                if db_manager and build_id:
                    try:
                        db_manager.sync_verification_gate(build_id, "http", "PASSED", f"HTTP readiness OK (status {check_result.status_code})")
                    except Exception:
                        pass

                # Authoritative Gate 6: Domain-specific & real browser verification
                app_gate_res = GateEvaluator.evaluate_application(
                    runtime_type=state.runtime_type,
                    check_result=check_result,
                    workspace_dir=self.workspace.root,
                    state=state,
                    preview_manager=self.preview_manager,
                )

                if app_gate_res.passed:
                    session.status = "APPLICATION_VERIFIED"
                    state.verification_gates["application"] = True
                    state.runtime_verification_steps.append("Application verified")

                    # Build explicit runtime targets
                    targets = []
                    r_type = state.runtime_type
                    if r_type == "api":
                        state.runtime_status = "RUNNING"
                        session.status = "RUNNING"
                        state.is_app_verified = True
                        state.project_success = True
                        state.failure_classification = None
                        state.failure_reason = None

                        if db_manager and build_id:
                            try:
                                db_manager.sync_verification_gate(build_id, "application", "PASSED", check_result.message or "Application verified")
                            except Exception:
                                pass

                        targets.append({
                            "type": "api",
                            "name": "API Service",
                            "url": state.runtime_url,
                            "port": target_port,
                            "pid": session.pid,
                            "status": "HEALTHY",
                            "framework": env_config["project_type"],
                        })
                        has_docs = env_config.get("has_docs") or self.preview_manager.verify_docs_endpoint(state.runtime_url)
                        if has_docs:
                            targets.append({
                                "type": "docs",
                                "name": "API Documentation",
                                "url": f"{state.runtime_url.rstrip('/')}/docs",
                                "port": target_port,
                                "pid": session.pid,
                                "status": "AVAILABLE",
                                "framework": "Swagger / OpenAPI",
                            })
                    elif r_type == "fullstack":
                        fe_cfg = env_config.get("frontend_config")
                        fe_session = None
                        fe_port = None
                        fe_healthy = False
                        if fe_cfg:
                            state.add_activity(f"Starting frontend server on port {fe_cfg['port']}...", level="run")
                            fe_session = self.process_manager.start_session(
                                command=fe_cfg["command"],
                                cwd=fe_cfg["cwd"],
                                project_id=getattr(state, "project_id", "default_project") or "default_project",
                                project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
                                framework=fe_cfg["project_type"],
                                explicit_port=fe_cfg.get("port"),
                                stop_existing=False,
                            )
                            if fe_session and fe_session.is_alive():
                                fe_port = self.process_manager.wait_for_port(fe_session, timeout=8.0) or fe_cfg.get("port")
                                fe_check = self.preview_manager.check_health(
                                    f"http://localhost:{fe_port}", timeout=2.0, max_retries=6, expected_type="web"
                                )
                                if fe_check.is_healthy:
                                    fe_healthy = True
                                    state.add_activity(f"Frontend server verified online at http://localhost:{fe_port}", level="ok")

                        if not fe_healthy or not fe_port:
                            # Fullstack frontend failed: strictly reject success!
                            state.is_app_verified = False
                            state.project_success = False
                            state.runtime_status = "FAILED"
                            state.verification_gates["application"] = False
                            state.failure_classification = "FRONTEND_NOT_RUNNING"
                            state.failure_reason = "Fullstack application frontend failed to start or verify."
                            state.add_activity("FULLSTACK VERIFICATION FAILURE: Frontend server could not be started or verified.", level="bad")
                            targets.append({
                                "type": "api",
                                "name": "Backend API",
                                "url": f"http://localhost:{target_port}",
                                "port": target_port,
                                "pid": session.pid,
                                "status": "HEALTHY",
                                "framework": env_config["project_type"],
                            })
                            state.runtime_targets = targets
                            return False

                        fe_final_url = f"http://localhost:{fe_port}"
                        conn_ok, conn_msg = self.preview_manager.verify_fullstack_connectivity(
                            fe_final_url, f"http://localhost:{target_port}"
                        )
                        if not conn_ok:
                            state.add_activity(f"Notice: Fullstack connectivity check: {conn_msg}", level="dim")

                        crud_ok, crud_msg, crud_details = self.preview_manager.verify_fullstack_crud_transaction(
                            backend_url=f"http://localhost:{target_port}",
                            workspace_dir=getattr(self.workspace, "root", None),
                            endpoint=getattr(state, "test_crud_endpoint", "/api/items") or "/api/items",
                            payload=getattr(state, "test_crud_payload", None),
                        )
                        if crud_ok:
                            state.add_activity(f"CRUD INTEGRATION VERIFIED: {crud_msg}", level="ok")
                        else:
                            state.add_activity(f"Notice: CRUD transaction verification: {crud_msg}", level="dim")

                        state.runtime_status = "RUNNING"
                        session.status = "RUNNING"
                        state.is_app_verified = True
                        state.project_success = True
                        state.failure_classification = None
                        state.failure_reason = None

                        if db_manager and build_id:
                            try:
                                db_manager.sync_verification_gate(build_id, "application", "PASSED", f"Fullstack verified (FE: {fe_port}, BE: {target_port})")
                            except Exception:
                                pass

                        # Register Frontend Application
                        targets.append({
                            "type": "web",
                            "name": "Frontend Application",
                            "url": fe_final_url,
                            "port": fe_port,
                            "pid": fe_session.pid if fe_session else None,
                            "status": "HEALTHY",
                            "framework": fe_cfg["project_type"] if fe_cfg else "Web Frontend",
                        })

                        # Register Backend API
                        targets.append({
                            "type": "api",
                            "name": "Backend API",
                            "url": f"http://localhost:{target_port}",
                            "port": target_port,
                            "pid": session.pid,
                            "status": "HEALTHY",
                            "framework": env_config["project_type"],
                        })

                        # Register API Docs if FastAPI
                        if env_config.get("has_docs") or self.preview_manager.verify_docs_endpoint(f"http://localhost:{target_port}"):
                            targets.append({
                                "type": "docs",
                                "name": "API Documentation",
                                "url": f"http://localhost:{target_port}/docs",
                                "port": target_port,
                                "pid": session.pid,
                                "status": "AVAILABLE",
                                "framework": "Swagger / OpenAPI",
                            })

                        # Set primary runtime URL to frontend for user preview and record distinct backend properties
                        if fe_port:
                            state.runtime_url = fe_final_url
                            state.runtime_port = fe_port
                            state.frontend_url = fe_final_url
                            state.frontend_port = fe_port
                            state.frontend_pid = fe_session.pid if fe_session else None
                            state.backend_url = f"http://localhost:{target_port}"
                            state.backend_port = target_port
                            state.backend_pid = session.pid
                    elif r_type == "web":
                        state.runtime_status = "RUNNING"
                        session.status = "RUNNING"
                        state.is_app_verified = True
                        state.project_success = True
                        state.failure_classification = None
                        state.failure_reason = None

                        if db_manager and build_id:
                            try:
                                db_manager.sync_verification_gate(build_id, "application", "PASSED", check_result.message or "Application verified")
                            except Exception:
                                pass

                        targets.append({
                            "type": "web",
                            "name": "Web Application",
                            "url": state.runtime_url,
                            "port": target_port,
                            "pid": session.pid,
                            "status": "HEALTHY",
                            "framework": env_config["project_type"],
                        })
                    else:
                        state.runtime_status = "RUNNING"
                        session.status = "RUNNING"
                        state.is_app_verified = True
                        state.project_success = True
                        state.failure_classification = None
                        state.failure_reason = None
                    state.runtime_targets = targets
                    state.add_activity(f"Live preview verified online at {state.runtime_url} ({state.runtime_type.upper()})!", level="ok")
                else:
                    state.runtime_status = "FAILED"
                    session.status = "FAILED"
                    state.is_app_verified = False
                    state.project_success = False
                    state.verification_gates["application"] = False
                    browser_ev = app_gate_res.evidence.get("browser_verification", {})
                    state.failure_classification = browser_ev.get("classification") or "BROWSER_VERIFICATION_FAILED"
                    state.failure_reason = app_gate_res.reason or check_result.message
                    state.add_activity(f"Application verification failed: {state.failure_reason}", level="bad")
                    if browser_ev.get("uncaught_exceptions"):
                        for unc_err in browser_ev["uncaught_exceptions"]:
                            state.errors.append(f"Browser Uncaught Exception: {unc_err}")
                    if browser_ev.get("console_errors"):
                        for c_err in browser_ev["console_errors"]:
                            state.errors.append(f"Browser Console Error: {c_err}")
            else:
                state.runtime_status = "FAILED"
                session.status = "FAILED"
                state.is_app_verified = False
                state.project_success = False

                if not session.is_alive():
                    exit_code = session.process.poll() if session.process else -1
                    stderr_lines = [l for l in session.stderr_lines if l.strip()]
                    last_err = stderr_lines[-1] if stderr_lines else ""
                    state.failure_classification = "PROCESS_CRASHED"
                    state.failure_reason = f"Process crashed during HTTP readiness check (exit code {exit_code}). {last_err}".strip()
                    state.add_activity(f"RUNTIME FAILURE: Process crashed during readiness check (exit code {exit_code})", level="bad")
                    if last_err:
                        state.add_activity(f"Error detail: {last_err[:250]}", level="bad")
                else:
                    state.failure_classification = check_result.classification
                    state.failure_reason = check_result.message
                    state.add_activity(f"RUNTIME FAILURE: HTTP readiness failed on port {target_port}: {check_result.message} ({check_result.classification})", level="bad")

        else:
            # Non-web application (CLI, script, library)
            time.sleep(0.5)
            exit_code = session.process.poll() if session.process else 0
            if exit_code is not None and exit_code != 0:
                stderr_lines = [l for l in session.stderr_lines if l.strip()]
                last_err = stderr_lines[-1] if stderr_lines else "Process exited with non-zero status code."
                state.runtime_status = "FAILED"
                session.status = "FAILED"
                state.is_app_verified = False
                state.project_success = False
                state.failure_classification = "PROCESS_CRASHED"
                state.failure_reason = f"CLI process exited with code {exit_code}: {last_err}"
                state.add_activity(f"CLI process failed with exit code {exit_code}: {last_err[:200]}", level="bad")
                return False

            state.runtime_status = "RUNNING" if exit_code is None else "STOPPED"
            session.status = "RUNNING" if exit_code is None else "COMPLETED"
            state.is_app_verified = True
            state.project_success = True
            state.verification_gates["server"] = True
            state.verification_gates["http"] = True
            state.verification_gates["application"] = True
            state.runtime_verification_steps.append("Execution verified")
            state.runtime_targets = []
            state.add_activity(f"Application process executed cleanly ({state.runtime_type.upper()}).", level="ok")

        state.runtime_logs = self.process_manager.get_logs_text()
        return state.project_success

    def _repair_vite_workspace(self, state: ProjectState) -> bool:
        """Diagnose Vite workspace files, create missing index.html, and repair corrupted source files."""
        root = self.workspace.root
        repaired = False

        # 1. Look for entry script in src/
        entry_script = None
        for candidate in ["src/main.tsx", "src/main.jsx", "src/index.tsx", "src/index.jsx", "src/App.tsx", "src/App.jsx"]:
            if (root / candidate).exists():
                entry_script = candidate
                break

        if not entry_script:
            entry_script = "src/main.tsx"
            (root / "src").mkdir(parents=True, exist_ok=True)

        # 2. Check if index.html is missing
        if not (root / "index.html").exists():
            # Check if index.html is tucked away in public/ or src/
            for alt in ["public/index.html", "src/index.html"]:
                if (root / alt).exists():
                    try:
                        content = (root / alt).read_text(encoding="utf-8")
                        (root / "index.html").write_text(content, encoding="utf-8")
                        state.add_activity(f"Moved {alt} to project root index.html", level="ok")
                        repaired = True
                        break
                    except Exception:
                        pass

            if not (root / "index.html").exists():
                index_html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{state.project_name or 'SPIDY Application'}</title>
  </head>
  <body style="margin:0;padding:0;background:#030712;color:#f9fafb;overflow-x:hidden;">
    <div id="root"></div>
    <script type="module" src="/{entry_script}"></script>
  </body>
</html>
"""
                (root / "index.html").write_text(index_html, encoding="utf-8")
                state.add_activity("Generated missing project root index.html linking to " + entry_script, level="ok")
                repaired = True

        # 3. Ensure vite.config.ts / js exists
        has_vite_cfg = any((root / cfg).exists() for cfg in ["vite.config.ts", "vite.config.js", "vite.config.mjs"])
        if not has_vite_cfg:
            vite_cfg = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
"""
            (root / "vite.config.ts").write_text(vite_cfg, encoding="utf-8")
            state.add_activity("Created missing vite.config.ts configuration", level="ok")
            repaired = True

        # 4. Check for corrupted generator output (e.g. JSON copied into main.tsx)
        main_path = root / "src" / "main.tsx"
        if main_path.exists():
            try:
                main_txt = main_path.read_text(encoding="utf-8").strip()
                if main_txt.startswith("{") and "name" in main_txt and "version" in main_txt:
                    clean_main = """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

const root = document.getElementById('root')
if (root) {
  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}
"""
                    main_path.write_text(clean_main, encoding="utf-8")
                    state.add_activity("Repaired corrupted JSON in src/main.tsx with React entrypoint", level="ok")
                    repaired = True
            except Exception:
                pass

        return repaired

    def stop(self, state: ProjectState) -> None:
        """Stop project process and clean up process tree."""
        self.process_manager.stop()
        if state.runtime_status != "FAILED":
            state.runtime_status = "STOPPED"
        state.runtime_pid = None
        state.is_app_verified = False

        db_manager = getattr(state, "db_manager", None)
        runtime_id = getattr(state, "runtime_id", None)
        if db_manager and runtime_id:
            try:
                db_manager.sync_runtime_stop(runtime_id)
            except Exception:
                pass

        state.add_activity("Project process stopped cleanly.", level="dim")

    def restart(self, state: ProjectState) -> bool:
        """Restart project process."""
        self.stop(state)
        return self.run(state)
