"""SPIDY — Autonomous Software Engineering Backend Server.

Provides high-performance WebSocket broadcasting, REST API endpoints,
and production static asset serving on port 8501.
"""

import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import threading
import socket
import sys
import time
from typing import Any, Dict, List, Optional, Set
import uuid

from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect
import uvicorn

from backend.core.active_context import ActiveProjectContext, get_active_context, set_active_context, clear_active_context
from backend.core.brand import APP_NAME, APP_TAGLINE, APP_VERSION
from backend.core.history_manager import HistoryManager
from backend.core.llm.model_router import get_model_router
from backend.core.task_classifier import TaskClassifier, TaskClassification
from backend.database import get_database_manager
from backend.orchestration.orchestrator import MultiAgentPipeline
from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState, Task, ActivityLog
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.process_manager import ProcessManager

load_dotenv()

# Workspace & Pipeline Singletons
workspace = WorkspaceManager()
process_manager = ProcessManager()
history_manager = HistoryManager()
db_manager = get_database_manager()
try:
    db_manager.initialize()
except Exception as _db_init_err:
    logging.getLogger("spidy.server").error(f"Failed to initialize SQLite database: {_db_init_err}")

runner = ProjectRunner(workspace, process_manager)
pipeline = MultiAgentPipeline(workspace, runner)
state = ProjectState()
state.files = workspace.load_all_files()
state.db_manager = db_manager
try:
    get_model_router().set_fallback_callback(lambda msg, lvl: state.add_activity(msg, level=lvl))
except Exception:
    pass

# Thread-safety lock for state mutations
state_lock = threading.Lock()
build_thread: threading.Thread = None


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check if process with given PID is currently active in the OS."""
    if not pid or pid <= 4:
        return False
    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def restore_project_state(
    project_id: str,
    target_state: ProjectState,
    db_mgr: Optional[Any],
    p_runner: ProjectRunner,
    p_pipeline: MultiAgentPipeline,
) -> bool:
    """Restore state from SQLite and workspace for a given project ID."""
    if not db_mgr or not project_id:
        return False

    try:
        proj = db_mgr.projects.get_project(project_id)
        if not proj:
            return False

        project_ws = WorkspaceManager.for_project(project_id)
        p_runner.workspace = project_ws
        p_pipeline.workspace = project_ws
        files = project_ws.load_all_files()

        builds = db_mgr.builds.get_builds_for_project(project_id, limit=1)
        latest_build = builds[0] if builds else None
        build_id = latest_build.get("build_id", "") if latest_build else ""

        active_ctx = ActiveProjectContext(
            project_id=project_id,
            project_name=proj.get("name") or "SPIDY Project",
            conversation_id=f"conv_{project_id}",
            build_id=build_id,
            task_graph_id=f"tg_{build_id}" if build_id else "",
            workspace_path=str(project_ws.root),
        )
        set_active_context(active_ctx)

        with state_lock:
            target_state.project_id = project_id
            target_state.active_context = active_ctx
            target_state.project_name = proj.get("name") or "SPIDY Project"
            target_state.goal = (latest_build.get("requirement") if latest_build else proj.get("description")) or ""
            target_state.detected_language = proj.get("detected_stack") or "Python"
            target_state.effective_language = target_state.detected_language
            target_state.build_id = build_id
            target_state.task_graph_id = f"tg_{build_id}" if build_id else ""
            if proj.get("architecture_summary"):
                target_state.architecture_summary = proj["architecture_summary"]
            target_state.files = files
            target_state.is_project_generated = bool(files)
            target_state.project_generation_status = "GENERATED" if files else "NOT_STARTED"

            # Reconstruct tasks from workspace files
            tasks_list = []
            if files:
                for idx, fname in enumerate(files.keys()):
                    tasks_list.append(
                        Task(
                            id=f"t-res-{idx+1}",
                            title=f"Generate {fname}",
                            phase="BUILD",
                            status="SUCCESS",
                            agent_assigned="Developer Agent",
                            file_path=fname,
                            is_required=True,
                            build_id=build_id,
                            project_id=project_id,
                            result="File restored from workspace",
                        )
                    )
                b_status = latest_build.get("status") if latest_build else ("COMPLETED" if files else "IDLE")
                if b_status == "COMPLETED":
                    tasks_list.append(
                        Task(
                            id="t-res-run",
                            title="Launch application server process",
                            phase="RUN",
                            status="SUCCESS",
                            agent_assigned="Tester & Runner Agent",
                            is_required=True,
                            build_id=build_id,
                            project_id=project_id,
                            result="Process execution verified",
                        )
                    )
                    tasks_list.append(
                        Task(
                            id="t-res-test",
                            title="Verify application health & runtime logs",
                            phase="TEST",
                            status="SUCCESS",
                            agent_assigned="Tester & Runner Agent",
                            is_required=True,
                            build_id=build_id,
                            project_id=project_id,
                            result="Health checks verified",
                        )
                    )
                    if any("readme" in f.lower() for f in files.keys()):
                        tasks_list.append(
                            Task(
                                id="t-res-doc",
                                title="Generate documentation and README",
                                phase="DOCUMENT",
                                status="SUCCESS",
                                agent_assigned="Documentation Agent",
                                is_required=False,
                                build_id=build_id,
                                project_id=project_id,
                                result="Documentation verified",
                            )
                        )
            target_state.tasks = tasks_list

            # Restore activities from SQLite
            if build_id:
                try:
                    db_activities = db_mgr.activity.get_activities_for_build(build_id, limit=80)
                    status_to_level = {"COMPLETED": "ok", "SUCCESS": "ok", "RUNNING": "run", "FAILED": "bad", "INFO": "dim"}
                    target_state.activity_feed = [
                        ActivityLog(
                            timestamp=a.get("timestamp", "").split("T")[-1][:8] if "T" in a.get("timestamp", "") else a.get("timestamp", ""),
                            message=a.get("message", ""),
                            level=status_to_level.get(a.get("status"), "ok"),
                        )
                        for a in db_activities
                    ]
                except Exception:
                    pass

            # Restore verification gates from SQLite
            if build_id:
                try:
                    gates = db_mgr.verification.get_gates_for_build(build_id)
                    for g in gates:
                        gname = g.get("gate_name")
                        if gname in target_state.verification_gates:
                            target_state.verification_gates[gname] = (g.get("status") == "PASSED")
                except Exception:
                    pass

            # Check runtime sessions
            if build_id:
                try:
                    runtimes = db_mgr.runtimes.get_sessions_for_build(build_id)
                    if runtimes:
                        latest_rt = runtimes[0]
                        rt_pid = latest_rt.get("pid")
                        if is_pid_alive(rt_pid):
                            target_state.runtime_pid = rt_pid
                            target_state.runtime_port = latest_rt.get("port")
                            target_state.runtime_url = latest_rt.get("url")
                            target_state.runtime_status = "RUNNING"
                            target_state.is_app_verified = True
                        else:
                            target_state.runtime_pid = None
                            target_state.runtime_port = latest_rt.get("port")
                            target_state.runtime_url = latest_rt.get("url")
                            target_state.runtime_status = "STOPPED"
                except Exception:
                    pass

            # Synchronize final phase and project_state
            b_status = latest_build.get("status") if latest_build else ("COMPLETED" if files else "IDLE")
            if b_status == "COMPLETED":
                target_state.current_phase = "COMPLETE"
                target_state.project_state = "SUCCESS"
                target_state.project_success = True
                target_state.failure_reason = None
                target_state.failure_classification = None
                target_state.errors = []
            elif b_status == "INTERRUPTED":
                target_state.current_phase = "FAILED"
                target_state.project_state = "FAILED"
                target_state.project_success = False
                target_state.failure_classification = "EXECUTION_INTERRUPTED"
                target_state.failure_reason = latest_build.get("failure_reason") or "Build interrupted unexpectedly"
                target_state.errors = [target_state.failure_reason]
            elif b_status == "FAILED":
                target_state.current_phase = "FAILED"
                target_state.project_state = "FAILED"
                target_state.project_success = False
                target_state.failure_classification = "EXECUTION_FAILURE"
                target_state.failure_reason = latest_build.get("failure_reason") or "Build failed"
                target_state.errors = [target_state.failure_reason]
            else:
                target_state.current_phase = "COMPLETE" if files else "DISCOVER"
                target_state.project_state = "SUCCESS" if files else "IDLE"
                target_state.project_success = bool(files)

            target_state.is_running = False

        return True
    except Exception as exc:
        logging.getLogger("spidy.server").warning(f"Error restoring project {project_id}: {exc}")
        return False


def reconcile_startup_state(db_mgr: Optional[Any], p_runner: ProjectRunner, p_pipeline: MultiAgentPipeline, target_state: ProjectState) -> None:
    """Reconcile orphaned in-progress builds and restore active project context on server startup."""
    if not db_mgr:
        return

    try:
        in_progress = db_mgr.builds.get_in_progress_builds()
        for b in in_progress:
            bid = b["build_id"]
            pid = b["project_id"]
            runtimes = db_mgr.runtimes.get_sessions_for_build(bid)
            has_alive_process = False
            for rt in runtimes:
                if is_pid_alive(rt.get("pid")):
                    has_alive_process = True
                    break

            if not has_alive_process:
                # Process died or server was terminated mid-build
                p_ws = WorkspaceManager.for_project(pid)
                ws_files = p_ws.list_files()
                if ws_files and len(ws_files) >= 3 and b.get("status") == "BUILDING":
                    db_mgr.sync_build_interrupted(
                        build_id=bid,
                        project_id=pid,
                        reason="Server was restarted while build was in progress. Workspace files preserved.",
                    )
                else:
                    db_mgr.sync_build_interrupted(
                        build_id=bid,
                        project_id=pid,
                        reason="Build process interrupted by server restart.",
                    )

        # Restore latest active project
        projects = db_mgr.projects.get_all_projects()
        if projects:
            latest_pid = projects[0].get("project_id")
            if latest_pid:
                restore_project_state(latest_pid, target_state, db_mgr, p_runner, p_pipeline)
    except Exception as exc:
        logging.getLogger("spidy.server").warning(f"Error reconciling startup state: {exc}")


# Run initial startup reconciliation
reconcile_startup_state(db_manager, runner, pipeline, state)


# Active WebSocket connections
active_websockets: Set[WebSocket] = set()
ws_lock = threading.Lock()
loop: asyncio.AbstractEventLoop = None


def get_current_loop() -> asyncio.AbstractEventLoop:
    global loop
    if loop is None or loop.is_closed():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    return loop


def broadcast_state_sync() -> None:
    """Thread-safe trigger to broadcast state over all connected WebSockets."""
    with state_lock:
        data = state.to_dict()
    payload = json.dumps({"type": "STATE_UPDATE", "state": data})

    with ws_lock:
        sockets = list(active_websockets)

    for ws in sockets:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(payload), get_current_loop())
        except Exception:
            pass


# Hook state activity feed to automatically broadcast events in real-time
original_add_activity = state.add_activity


def hooked_add_activity(message: str, level: str = "ok") -> None:
    original_add_activity(message, level=level)
    build_id = getattr(state, "build_id", None)
    if db_manager and build_id:
        try:
            status_map = {"ok": "COMPLETED", "run": "RUNNING", "bad": "FAILED", "dim": "INFO"}
            db_manager.sync_activity(
                build_id=build_id,
                message=message,
                event_type="ACTIVITY",
                agent=getattr(state, "active_agent", "Orchestrator"),
                status=status_map.get(level, "INFO"),
            )
        except Exception:
            pass
    broadcast_state_sync()


state.add_activity = hooked_add_activity


# Background Build Worker
# Background Build Worker
def _run_build_worker(goal: str, language: str, project_id: Optional[str] = None) -> None:
    global state
    if project_id and project_id != "spidy-default":
        target_pid = project_id
        project_name = getattr(state, "project_name", "SPIDY Project") or "SPIDY Project"
    else:
        target_pid = f"proj_{int(time.time())}_{uuid.uuid4().hex[:4]}"
        project_name = "SPIDY Project"

    build_id = f"bld_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    active_ctx = ActiveProjectContext.create_new(
        project_name=project_name,
        project_id=target_pid,
        build_id=build_id,
    )
    set_active_context(active_ctx)

    # Workspace isolation per project
    project_ws = WorkspaceManager.for_project(target_pid)
    runner.workspace = project_ws
    pipeline.workspace = project_ws

    with state_lock:
        state.reset(new_goal=goal, language=language, project_id=target_pid, build_id=build_id)
        state.conversation_id = active_ctx.conversation_id
        state.active_context = active_ctx
        state.db_manager = db_manager
        state.build_start_time = time.time()
        state.is_running = True

    try:
        db_manager.sync_project_and_build_start(
            project_id=target_pid,
            project_name=project_name,
            build_id=build_id,
            requirement=goal,
            detected_stack=language,
            workspace_path=str(project_ws.root),
            estimated_duration=state.estimated_duration_str,
        )
    except Exception as _sync_err:
        logging.getLogger("spidy.server").warning(f"Error syncing build start to SQLite: {_sync_err}")

    broadcast_state_sync()

    try:
        pipeline.analyze_and_plan(state)
        broadcast_state_sync()

        if state.user_approved:
            pipeline.execute_build(state)
            broadcast_state_sync()
            final_status = "COMPLETED" if state.project_success else ("FAILED" if (state.errors or state.failure_reason) else "FINISHED")
            duration = time.time() - state.build_start_time if state.build_start_time else None
            try:
                db_manager.sync_build_finish(
                    build_id=build_id,
                    project_id=target_pid,
                    status=final_status,
                    duration=duration,
                    final_result=state.architecture_summary or ("Success" if state.project_success else None),
                    failure_reason=state.failure_reason,
                    detected_stack=state.effective_language,
                )
            except Exception:
                pass
        else:
            try:
                db_manager.sync_activity(
                    build_id=build_id,
                    message="Plan generated. Waiting for user approval.",
                    event_type="WAITING",
                    agent="Orchestrator",
                    status="WAITING_FOR_USER",
                )
            except Exception:
                pass
    except Exception as exc:
        with state_lock:
            state.fail(f"Build failed with exception: {exc}")
            state.is_running = False
        duration = time.time() - state.build_start_time if state.build_start_time else None
        try:
            db_manager.sync_build_finish(
                build_id=build_id,
                project_id=target_pid,
                status="FAILED",
                duration=duration,
                failure_reason=str(exc),
                detected_stack=state.effective_language,
            )
        except Exception:
            pass
        broadcast_state_sync()
    finally:
        with state_lock:
            state.is_running = False
        broadcast_state_sync()


# REST Handlers
async def api_get_state(request):
    with state_lock:
        return JSONResponse(state.to_dict())


async def api_post_build(request):
    global build_thread
    data = await request.json()
    goal = (data.get("goal") or "").strip()
    language = data.get("language", "Auto Detect")

    if not goal:
        return JSONResponse({"error": "Please provide a programming requirement."}, status_code=400)

    router = get_model_router()
    if not router.is_configured():
        return JSONResponse(
            {"error": "AI provider credentials not configured. Please check .env settings."},
            status_code=400,
        )

    project_id = data.get("project_id")
    # If a build is currently recorded as running, stop it and start the requested build cleanly
    if state.is_running:
        if build_thread is not None and build_thread.is_alive():
            try:
                runner.stop(state)
                pipeline.workspace.clear_workspace()
            except Exception:
                pass
        with state_lock:
            state.is_running = False

    build_thread = threading.Thread(target=_run_build_worker, args=(goal, language, project_id), daemon=True)
    build_thread.start()

    return JSONResponse({"message": "Build started successfully.", "goal": goal, "language": language, "project_id": project_id})


def _run_conversational_worker(message: str, project_id: Optional[str] = None, language: str = "Auto Detect") -> None:
    global state

    # Pre-classify intent to check if this is an explicit or implicit NEW PROJECT
    has_existing = bool(
        project_id
        and project_id != "spidy-default"
        and db_manager
        and db_manager.projects.get_project(project_id)
    )
    existing_files_count = len(WorkspaceManager.for_project(project_id).list_files()) if has_existing else 0
    classification = TaskClassifier.classify(
        message=message,
        has_existing_project=has_existing,
        existing_files_count=existing_files_count,
    )

    if classification == TaskClassification.NEW_PROJECT or not has_existing:
        # Route to fresh isolated build worker so new project lifecycle is clean
        _run_build_worker(goal=message, language=language, project_id=None)
        return

    target_pid = project_id
    build_id = f"bld_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    active_ctx = ActiveProjectContext.create_new(
        project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
        project_id=target_pid,
        build_id=build_id,
    )
    set_active_context(active_ctx)

    # Workspace isolation per project
    project_ws = WorkspaceManager.for_project(target_pid)
    runner.workspace = project_ws
    pipeline.workspace = project_ws

    with state_lock:
        state.build_id = build_id
        state.task_graph_id = f"tg_{build_id}"
        state.project_id = target_pid
        state.active_context = active_ctx
        state.db_manager = db_manager
        state.build_start_time = time.time()
        state.is_running = True
        # Cleanly purge stale failed tasks so old build errors never fail new delta turn
        state.tasks = [t for t in state.tasks if t.status in ("SUCCESS", "completed")]
        state.errors = []
        state.failure_reason = None
        state.known_issues = []
        state.reviewer_verdict = None

    if db_manager:
        try:
            db_manager.sync_project_and_build_start(
                project_id=target_pid,
                project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
                build_id=build_id,
                requirement=message,
                detected_stack=language,
                workspace_path=str(project_ws.root),
                estimated_duration=state.estimated_duration_str,
            )
        except Exception as _sync_err:
            logging.getLogger("spidy.server").warning(f"Error syncing conversational build start: {_sync_err}")

    broadcast_state_sync()

    try:
        pipeline.execute_conversational_turn(state, message, selected_language=language)
        broadcast_state_sync()
        final_status = "COMPLETED" if state.project_success else ("FAILED" if (state.errors or state.failure_reason) else "FINISHED")
        duration = time.time() - state.build_start_time if state.build_start_time else None
        if db_manager:
            try:
                db_manager.sync_build_finish(
                    build_id=build_id,
                    project_id=target_pid,
                    status=final_status,
                    duration=duration,
                    final_result=state.architecture_summary or ("Success" if state.project_success else None),
                    failure_reason=state.failure_reason,
                    detected_stack=state.effective_language,
                )
            except Exception:
                pass
    except Exception as exc:
        with state_lock:
            state.fail(f"Conversational update failed: {exc}")
            state.is_running = False
        duration = time.time() - state.build_start_time if state.build_start_time else None
        if db_manager:
            try:
                db_manager.sync_build_finish(
                    build_id=build_id,
                    project_id=target_pid,
                    status="FAILED",
                    duration=duration,
                    failure_reason=str(exc),
                    detected_stack=state.effective_language,
                )
            except Exception:
                pass
        broadcast_state_sync()
    finally:
        with state_lock:
            state.is_running = False
        broadcast_state_sync()


async def api_post_chat(request):
    global build_thread
    data = await request.json()
    message = (data.get("message") or "").strip()
    project_id = data.get("project_id")
    language = data.get("language", "Auto Detect")

    if not message:
        return JSONResponse({"error": "Message is required."}, status_code=400)

    router = get_model_router()
    if not router.is_configured():
        return JSONResponse(
            {"error": "AI provider credentials not configured."},
            status_code=400,
        )

    if state.is_running:
        return JSONResponse(
            {"error": "A task is currently running. Please wait for it to complete."},
            status_code=409,
        )

    build_thread = threading.Thread(
        target=_run_conversational_worker,
        args=(message, project_id, language),
        daemon=True,
    )
    build_thread.start()

    return JSONResponse({
        "message": "Instruction queued.",
        "project_id": project_id or state.project_id,
        "input": message,
    })


async def api_post_stop(request):
    with state_lock:
        runner.stop(state)
        pipeline.workspace.clear_workspace()
        state.reset()
    broadcast_state_sync()
    return JSONResponse({"message": "Workspace reset and processes terminated."})


async def api_post_approve(request):
    global build_thread
    data = await request.json()
    answers = data.get("answers", {})

    with state_lock:
        state.clarification_answers = answers
        state.user_approved = True

    def _continue_after_approval():
        build_id = getattr(state, "build_id", None)
        project_id = getattr(state, "project_id", "spidy-default") or "spidy-default"
        try:
            pipeline.execute_build(state)
            if db_manager and build_id:
                final_status = "COMPLETED" if state.project_success else ("FAILED" if (state.errors or state.failure_reason) else "FINISHED")
                duration = time.time() - state.build_start_time if state.build_start_time else None
                try:
                    db_manager.sync_build_finish(
                        build_id=build_id,
                        project_id=project_id,
                        status=final_status,
                        duration=duration,
                        final_result=state.architecture_summary or ("Success" if state.project_success else None),
                        failure_reason=state.failure_reason,
                        detected_stack=state.effective_language,
                    )
                except Exception:
                    pass
        except Exception as exc:
            if db_manager and build_id:
                duration = time.time() - state.build_start_time if state.build_start_time else None
                try:
                    db_manager.sync_build_finish(
                        build_id=build_id,
                        project_id=project_id,
                        status="FAILED",
                        duration=duration,
                        failure_reason=str(exc),
                        detected_stack=state.effective_language,
                    )
                except Exception:
                    pass
        finally:
            with state_lock:
                state.is_running = False
            broadcast_state_sync()

    build_thread = threading.Thread(target=_continue_after_approval, daemon=True)
    build_thread.start()

    return JSONResponse({"message": "Approved. Build commenced."})


async def api_get_files(request):
    files = pipeline.workspace.load_all_files()
    return JSONResponse({"files": files})


async def api_get_diagnostics(request):
    router = get_model_router()
    db_diagnostics = {}
    if db_manager:
        try:
            db_diagnostics = db_manager.get_diagnostics()
        except Exception as exc:
            db_diagnostics = {"status": "ERROR", "error": str(exc)}
    return JSONResponse({
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "model_router": router.get_diagnostics(),
        "database": db_diagnostics,
        "verification_gates": state.verification_gates,
        "runtime_status": state.runtime_status,
        "runtime_port": state.runtime_port,
        "runtime_pid": state.runtime_pid,
        "recovery_attempts": state.recovery_attempts,
    })


# WebSocket Handler
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    with ws_lock:
        active_websockets.add(websocket)

    # Immediately send current state on connect
    with state_lock:
        init_payload = json.dumps({"type": "STATE_UPDATE", "state": state.to_dict()})
    await websocket.send_text(init_payload)

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                action = data.get("action")
                if action == "GET_STATE":
                    with state_lock:
                        await websocket.send_text(
                            json.dumps({"type": "STATE_UPDATE", "state": state.to_dict()})
                        )
                elif action == "BUILD":
                    goal = (data.get("goal") or "").strip()
                    lang = data.get("language", "Auto Detect")
                    if goal and not state.is_running:
                        threading.Thread(
                            target=_run_build_worker, args=(goal, lang), daemon=True
                        ).start()
                elif action == "STOP":
                    with state_lock:
                        runner.stop(state)
                        workspace.clear_workspace()
                        state.reset()
                    broadcast_state_sync()
            except Exception:
                pass
    except WebSocketDisconnect:
        with ws_lock:
            active_websockets.discard(websocket)


async def handle_legacy_streamlit_ws(websocket: WebSocket):
    """Gracefully terminate stale Streamlit websocket probes from cached browser tabs."""
    try:
        await websocket.accept()
        await websocket.close(code=1000, reason="Streamlit runtime inactive; SPIDY engine active.")
    except Exception:
        pass


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><polygon points="16,2 30,16 16,30 2,16" fill="#040711" stroke="#38bdf8" stroke-width="2"/><circle cx="16" cy="16" r="4" fill="#38bdf8"/></svg>"""


async def favicon_handler(request):
    return Response(FAVICON_SVG, media_type="image/svg+xml")


async def api_get_history(request):
    try:
        builds = db_manager.builds.get_recent_builds(limit=50)
        if builds:
            items = []
            for b in builds:
                proj = db_manager.projects.get_project(b.get("project_id", "")) or {}
                dur_secs = b.get("duration") or 0.0
                mins = int(dur_secs) // 60
                secs = int(dur_secs) % 60
                dur_str = f"{mins}m {secs}s" if dur_secs > 0 else "N/A"
                items.append({
                    "project_id": b.get("project_id", ""),
                    "project_name": proj.get("name", "SPIDY Project"),
                    "goal": b.get("requirement", ""),
                    "tech_stack": proj.get("detected_stack") or "Fullstack",
                    "status": b.get("status", "COMPLETED"),
                    "actual_duration_str": dur_str,
                    "actual_duration_seconds": dur_secs,
                    "estimate_range": b.get("estimated_duration") or "~8–12 MIN",
                    "timestamp": b.get("created_at", ""),
                    "build_id": b.get("build_id", ""),
                })
            return JSONResponse({"history": items})
    except Exception as exc:
        logging.getLogger("spidy.server").warning(f"Error querying SQLite history: {exc}")

    items = history_manager.get_history()
    return JSONResponse({"history": items})


async def api_get_projects(request):
    try:
        projects = db_manager.projects.get_all_projects()
        return JSONResponse({"projects": projects})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_get_project_detail(request):
    project_id = request.path_params.get("project_id")
    try:
        project = db_manager.projects.get_project(project_id)
        if not project:
            return JSONResponse({"error": "Project not found"}, status_code=404)
        builds = db_manager.builds.get_builds_for_project(project_id)
        return JSONResponse({"project": project, "builds": builds})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_get_build_detail(request):
    build_id = request.path_params.get("build_id")
    try:
        build = db_manager.builds.get_build(build_id)
        if not build:
            return JSONResponse({"error": "Build not found"}, status_code=404)
        activities = db_manager.activity.get_activities_for_build(build_id, limit=200)
        agent_runs = db_manager.agents.get_runs_for_build(build_id)
        runtimes = db_manager.runtimes.get_sessions_for_build(build_id)
        verification = db_manager.verification.get_gates_for_build(build_id)
        return JSONResponse({
            "build": build,
            "activities": activities,
            "agent_runs": agent_runs,
            "runtimes": runtimes,
            "verification": verification,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_post_runtime_control(request):
    data = await request.json()
    action = data.get("action")
    if action == "restart":
        def _restart_bg():
            with state_lock:
                runner.stop(state)
                broadcast_state_sync()
            time.sleep(0.5)
            with state_lock:
                runner.run(state)
                broadcast_state_sync()
        threading.Thread(target=_restart_bg, daemon=True).start()
        return JSONResponse({"message": "Runtime restart initiated."})
    elif action == "stop":
        with state_lock:
            runner.stop(state)
            state.runtime_status = "STOPPED"
        broadcast_state_sync()
        return JSONResponse({"message": "Runtime stopped."})
    elif action == "start":
        def _start_bg():
            with state_lock:
                runner.run(state)
                broadcast_state_sync()
        threading.Thread(target=_start_bg, daemon=True).start()
        return JSONResponse({"message": "Runtime start initiated."})
    return JSONResponse({"error": "Unknown action"}, status_code=400)


async def api_get_project_messages(request):
    project_id = request.path_params.get("project_id")
    if not db_manager:
        return JSONResponse({"messages": []})
    try:
        messages = db_manager.messages.get_messages_for_project(project_id)
        return JSONResponse({"project_id": project_id, "messages": messages})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


async def api_post_resume_project(request):
    project_id = request.path_params.get("project_id")
    if not db_manager:
        return JSONResponse({"error": "Database not initialized"}, status_code=500)

    success = restore_project_state(project_id, state, db_manager, runner, pipeline)
    if not success:
        return JSONResponse({"error": "Failed to resume project or project not found"}, status_code=404)

    broadcast_state_sync()
    proj = db_manager.projects.get_project(project_id)
    return JSONResponse({"message": "Project resumed successfully", "project": proj})



# Routes
routes = [
    Route("/api/state", api_get_state, methods=["GET"]),
    Route("/api/build", api_post_build, methods=["POST"]),
    Route("/api/chat", api_post_chat, methods=["POST"]),
    Route("/api/stop", api_post_stop, methods=["POST"]),
    Route("/api/approve", api_post_approve, methods=["POST"]),
    Route("/api/files", api_get_files, methods=["GET"]),
    Route("/api/diagnostics", api_get_diagnostics, methods=["GET"]),
    Route("/api/history", api_get_history, methods=["GET"]),
    Route("/api/projects", api_get_projects, methods=["GET"]),
    Route("/api/projects/{project_id}", api_get_project_detail, methods=["GET"]),
    Route("/api/projects/{project_id}/messages", api_get_project_messages, methods=["GET"]),
    Route("/api/projects/{project_id}/resume", api_post_resume_project, methods=["POST"]),
    Route("/api/builds/{build_id}", api_get_build_detail, methods=["GET"]),
    Route("/api/runtime/control", api_post_runtime_control, methods=["POST"]),
    Route("/favicon.ico", favicon_handler, methods=["GET"]),
    Route("/.well-known/{path:path}", lambda r: JSONResponse({}), methods=["GET"]),
    Route("/_stcore/{path:path}", lambda r: Response("Streamlit disabled", status_code=404), methods=["GET", "POST"]),
    WebSocketRoute("/_stcore/{path:path}", handle_legacy_streamlit_ws),
    WebSocketRoute("/ws", websocket_endpoint),
]

# Static frontend mounting and clean SPA routing
frontend_dist = Path(__file__).parent / "frontend" / "dist"
index_html_path = frontend_dist / "index.html"
assets_dist = frontend_dist / "assets"


async def spa_index_response():
    if not index_html_path.exists():
        return Response("SPIDY frontend not built. Please run 'npm run build' in frontend/.", status_code=503)
    content = index_html_path.read_text(encoding="utf-8")
    return Response(
        content,
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


async def api_spa_root(request):
    return await spa_index_response()


async def api_static_media_fallback(request):
    """Cleanly return 404 for stale or non-existent static media assets (e.g. legacy Streamlit assets)."""
    return Response("Not Found", status_code=404)


async def api_spa_catchall(request):
    path = request.url.path
    # Return 404 for missing static assets, legacy Streamlit probes, images, fonts, scripts
    if (
        "." in Path(path).name
        or path.startswith("/static/")
        or path.startswith("/media/")
        or path.startswith("/_stcore")
    ):
        return Response("Not Found", status_code=404)
    # Return index.html for client-side SPA navigation routes
    return await spa_index_response()


if frontend_dist.exists() and index_html_path.exists():
    if assets_dist.exists():
        routes.append(Mount("/assets", StaticFiles(directory=str(assets_dist)), name="assets"))
    routes.append(Route("/", api_spa_root, methods=["GET"]))
    routes.append(Route("/static/{path:path}", api_static_media_fallback, methods=["GET"]))
    routes.append(Route("/{full_path:path}", api_spa_catchall, methods=["GET"]))

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(routes=routes, middleware=middleware)


def is_safe_to_reclaim_process(pid: int) -> bool:
    """Verify that PID belongs to a user-space dev server / runtime process and not an OS process."""
    if pid <= 4 or pid == os.getpid():
        return False
    try:
        import subprocess
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=2,
        )
        parts = [p.strip(' "\r\n') for p in out.split(",") if p.strip()]
        if parts:
            img = parts[0].lower()
            protected = ("system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe", "lsass.exe", "svchost.exe")
            if any(p in img for p in protected):
                return False
            return True
    except Exception:
        pass
    return False


def reclaim_port(port: int) -> None:
    """Terminate any orphaned or conflicting processes holding the given port safely."""
    current_pid = os.getpid()
    if sys.platform != "win32":
        return
    try:
        import subprocess
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=3,
        )
        target = f":{port}"
        pids_to_kill = set()
        for line in out.splitlines():
            line = line.strip()
            if "LISTENING" in line and target in line:
                parts = line.split()
                if len(parts) >= 5 and parts[-1].isdigit():
                    p = int(parts[-1])
                    if p != current_pid and p > 4 and is_safe_to_reclaim_process(p):
                        pids_to_kill.add(p)
        for p in pids_to_kill:
            print(f"[*] Reclaiming port {port} from conflicting process (PID {p})...")
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(p)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5,
                )
            except Exception:
                pass
        if pids_to_kill:
            time.sleep(0.8)
    except Exception:
        pass



def bind_server_socket(port: int, max_retries: int = 3) -> Optional[socket.socket]:
    """Attempt to create and bind an exclusive listening TCP socket on the given port."""
    reclaim_port(port)
    for attempt in range(max_retries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            sock.listen(128)
            return sock
        except OSError:
            sock.close()
            if attempt == 0:
                reclaim_port(port)
            time.sleep(0.5)
    return None


_bg_server_thread: Optional[threading.Thread] = None
_bg_server_port: Optional[int] = None
_bg_server_lock = threading.Lock()


class SuppressLegacyProbesFilter(logging.Filter):
    """Filter out noise from stale Streamlit browser tabs and Chrome DevTools probes."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return (
            "/_stcore" not in msg
            and "snowflake" not in msg
            and "MaterialSymbols" not in msg
            and "com.chrome.devtools.json" not in msg
            and "/.well-known/" not in msg
        )


def get_uvicorn_log_config() -> dict:
    """Return Uvicorn logging configuration with probe suppression filters."""
    cfg = copy.deepcopy(uvicorn.config.LOGGING_CONFIG)
    cfg["filters"] = {"suppress_legacy": {"()": SuppressLegacyProbesFilter}}
    if "uvicorn.access" in cfg.get("loggers", {}):
        cfg["loggers"]["uvicorn.access"]["filters"] = ["suppress_legacy"]
    return cfg


def start_background_server(preferred_port: int = 8502) -> int:
    """Start the Starlette/Uvicorn server in a background daemon thread."""
    global _bg_server_thread, _bg_server_port
    with _bg_server_lock:
        if _bg_server_thread is not None and _bg_server_thread.is_alive() and _bg_server_port:
            return _bg_server_port

        sock = None
        active_port = None
        for port in [preferred_port, 8501, 8503, 8500, 8080]:
            sock = bind_server_socket(port)
            if sock is not None:
                active_port = port
                break

        if sock is None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", 0))
            sock.listen(128)
            active_port = sock.getsockname()[1]

        _bg_server_port = active_port
        config = uvicorn.Config(app, log_level="info", log_config=get_uvicorn_log_config())
        server = uvicorn.Server(config)

        _bg_server_thread = threading.Thread(
            target=server.run,
            kwargs={"sockets": [sock]},
            daemon=True,
            name="SPIDY-Server-Thread",
        )
        _bg_server_thread.start()
        time.sleep(0.5)
        print(f"[*] {APP_NAME} background engine online at http://localhost:{active_port}")
        return active_port


def main(preferred_port: int = 8501):
    target_ports = [preferred_port]
    for p in [8501, 8502, 8503, 8500, 8080]:
        if p not in target_ports:
            target_ports.append(p)

    sock = None
    active_port = None
    for port in target_ports:
        sock = bind_server_socket(port)
        if sock is not None:
            active_port = port
            break
        print(f"[!] Port {port} is busy or restricted. Trying next candidate...")

    if sock is None:
        # Ultimate fallback: let OS pick an available ephemeral port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", 0))
        sock.listen(128)
        active_port = sock.getsockname()[1]

    print(f"[*] {APP_NAME} Control Server active on http://localhost:{active_port}")
    config = uvicorn.Config(app, log_level="info", log_config=get_uvicorn_log_config())
    server = uvicorn.Server(config)
    try:
        server.run(sockets=[sock])
    except (KeyboardInterrupt, SystemExit):
        pass
    except BaseException as exc:
        if "CancelledError" in type(exc).__name__:
            pass
        else:
            raise
    finally:
        try:
            sock.close()
        except Exception:
            pass
        print(f"\n[*] {APP_NAME} Control Server stopped cleanly.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
    except BaseException as exc:
        if "CancelledError" in type(exc).__name__:
            sys.exit(0)
        raise

