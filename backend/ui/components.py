"""Curated Creative-Tech UI components for NOVA Code Lab.

Implements typography-driven, minimal, split-composition presentation layers,
cinematic state visualization, dynamic build estimation, and progressive-disclosure drawers.
"""

from pathlib import Path
from typing import Dict, List, Optional
import streamlit as st

from backend.core.brand import APP_NAME, APP_TAGLINE, APP_VERSION, APP_HERO_SUBTITLE
from backend.core.estimation import BuildEstimator
from backend.core.history_manager import HistoryManager, ProjectRecord
from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState, PHASES
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.process_manager import ProcessManager
from backend.runtime.runtime_session import SPIDY_CONTROL_PORTS
from backend.ui.visual_canvas import get_state_canvas_html


import streamlit.components.v1 as components


def _render_canvas(html_str: str, height: int = 560) -> None:
    """Render 3D WebGL computational world using streamlit.components.v1.html."""
    components.html(html_str, height=height, scrolling=False)



def render_minimal_nav(
    active_drawer: Optional[str],
    state: ProjectState,
    api_online: bool,
    model_name: str,
) -> Optional[str]:
    """Renders the top minimal navigation bar."""
    status_label = state.project_state
    if state.current_phase == "COMPLETE":
        status_label = "VERIFIED"
    elif state.current_phase in ("BUILD", "PLAN", "ARCHITECT"):
        status_label = "BUILDING"
    elif state.runtime_status == "RUNNING":
        status_label = "RUNNING"
    elif state.current_phase == "BLOCKED":
        status_label = "BLOCKED"
    elif state.current_phase == "FAILED":
        if state.failure_classification in ("EXECUTION_INTERRUPTED", "SERVER_RESTARTED_MID_BUILD", "USER_CANCELLED"):
            status_label = "INTERRUPTED"
        else:
            status_label = "FAILED"


    col_brand, col_nav, col_stat = st.columns([1.5, 3.5, 2.0])

    with col_brand:
        st.markdown(
            f"""
            <div class="nova-brand">
              {APP_NAME} <span class="nova-brand-badge">{APP_VERSION}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_nav:
        nav_cols = st.columns(5)
        drawers = ["Projects", "Workspace", "Activity", "Runtime", "Diagnostics"]
        selected_drawer = active_drawer

        for i, name in enumerate(drawers):
            with nav_cols[i]:
                is_active = active_drawer == name
                label = f"• {name}" if is_active else name
                if st.button(label, key=f"nav_btn_{name}", use_container_width=True):
                    # Toggle drawer
                    selected_drawer = None if is_active else name

    with col_stat:
        st.markdown(
            f"""
            <div style="display:flex;justify-content:flex-end;align-items:center;gap:1.2rem;padding-top:0.4rem;">
              <div class="nova-status-pill">
                <span class="status-dot"></span>
                <span>{status_label}</span>
              </div>
              <div style="font-family:var(--font-mono);font-size:0.7rem;letter-spacing:0.12em;color:#64748b;">
                {model_name.split('/')[-1] if model_name else 'AI CORE'}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    return selected_drawer


def render_home_hero(state: ProjectState, api_online: bool) -> None:
    """Renders full-viewport landing composition when no project is actively running."""
    col_left, col_right = st.columns([1.0, 1.45], gap="large")

    with col_left:
        st.markdown(
            f"""
            <div style="padding-top: 1.5rem;">
              <div class="nova-hero-sub">{APP_TAGLINE}</div>
              <div class="nova-hero-huge">
                AI THAT<br>
                BUILDS<br>
                <span class="nova-text-gradient">SOFTWARE.</span>
              </div>
              <div style="font-family:var(--font-body);font-size:1.05rem;color:#94a3b8;line-height:1.6;max-width:520px;margin-bottom:2rem;">
                {APP_HERO_SUBTITLE}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_right:
        # 3D Computational World & Agent Constellation
        canvas_html = get_state_canvas_html("IDLE", height=580)
        _render_canvas(canvas_html, height=580)


def render_active_build(state: ProjectState) -> None:
    """Renders the split-composition active workspace during building, verifying, or running."""
    # Operation title based on phase
    op_title = "BUILDING THE APPLICATION"
    if state.current_phase in ("PLAN", "ARCHITECT"):
        op_title = "ARCHITECTING SYSTEM"
    elif state.current_phase == "RUN":
        op_title = "LAUNCHING RUNTIME"
    elif state.current_phase in ("TEST", "REVIEW"):
        op_title = "VERIFYING INTEGRITY"
    elif state.current_phase == "DEBUG":
        op_title = "AUTONOMOUS DEBUGGING"

    col_left, col_center, col_right = st.columns([1.1, 1.8, 1.0], gap="medium")

    with col_left:
        st.markdown(
            f"""
            <div style="padding-top: 0.6rem;">
              <div class="nova-hero-sub">PROJECT</div>
              <div style="font-family:var(--font-display);font-size:clamp(1.8rem, 2.8vw, 3.2rem);font-weight:800;letter-spacing:-0.03em;color:#ffffff;line-height:1.05;margin-bottom:1.2rem;">
                {state.project_name}
              </div>
              <div class="nova-hero-sub" style="color:var(--accent-indigo);">{op_title}</div>
              <div style="font-family:var(--font-mono);font-size:0.85rem;color:#cbd5e1;margin-bottom:1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
                {f"Target: <code>{state.current_file_target}</code>" if state.current_file_target else state.current_task_description}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Compact Stage Indicator
        stages = [("ARCHITECT", "ARCHITECT"), ("BUILD", "BUILD"), ("RUN", "RUN"), ("VERIFY", "COMPLETE")]
        phase_order = ["DISCOVER", "PLAN", "ARCHITECT", "BUILD", "RUN", "TEST", "DEBUG", "REVIEW", "DOCUMENT", "COMPLETE"]
        curr_idx = phase_order.index(state.current_phase) if state.current_phase in phase_order else 0

        pills = []
        for name, p_key in stages:
            target_idx = phase_order.index(p_key)
            if curr_idx > target_idx or (p_key == "COMPLETE" and state.project_success):
                pills.append(f'<span class="nova-stage-pill completed">✓ {name}</span>')
            elif curr_idx == target_idx:
                pills.append(f'<span class="nova-stage-pill active">● {name}</span>')
            else:
                pills.append(f'<span class="nova-stage-pill waiting">○ {name}</span>')

        st.markdown(f'<div class="nova-stage-strip">{"".join(pills)}</div>', unsafe_allow_html=True)

        # Minimal Cinematic Activity Stream (latest 3-4 items)
        recent_feed = state.activity_feed[-4:] if state.activity_feed else []
        stream_items = []
        for item in reversed(recent_feed):
            agent_tag = state.active_agent.split()[0].upper()
            stream_items.append(
                f"""
                <div class="nova-stream-item active">
                  <span class="nova-stream-agent">{agent_tag}</span>
                  <span class="nova-stream-msg">{item.message}</span>
                </div>
                """
            )

        if stream_items:
            st.markdown(f'<div class="nova-stream">{"".join(stream_items)}</div>', unsafe_allow_html=True)

    with col_center:
        mode = "BUILDING"
        if state.current_phase == "DEBUG":
            mode = "DEBUGGING"
        elif state.current_phase in ("TEST", "RUN"):
            mode = "VERIFYING"
        elif state.current_phase in ("PLAN", "ARCHITECT"):
            mode = "PLANNING"

        canvas_html = get_state_canvas_html(mode, height=480, active_agent=state.active_agent)
        _render_canvas(canvas_html, height=480)

    with col_right:
        counts = state.task_counts
        st.markdown(
            f"""
            <div style="padding-left: 0.5rem; border-left: 1px solid var(--border-subtle);">
              <div class="nova-stat-block">
                <div class="nova-stat-val" style="color:var(--accent-violet);">{state.estimated_duration_str}</div>
                <div class="nova-stat-lbl">ESTIMATED DURATION ({state.estimated_confidence} CONF.)</div>
              </div>

              <div class="nova-stat-block">
                <div class="nova-stat-val">{state.formatted_elapsed}</div>
                <div class="nova-stat-lbl">ELAPSED TIME</div>
              </div>

              <div class="nova-stat-block">
                <div class="nova-stat-val">{state.progress_percentage}%</div>
                <div class="nova-stat-lbl">PROGRESS ({counts['completed']} / {counts['total']} TASKS)</div>
              </div>

              <div class="nova-stat-block" style="margin-bottom:0.5rem;">
                <div class="nova-stat-val" style="font-size:1.8rem;">{state.agent_count} AGENTS</div>
                <div class="nova-stat-lbl">TEAM CAPACITY • {state.estimated_complexity} COMPLEXITY</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_success_view(state: ProjectState) -> None:
    """Renders the cinematic completion presentation when a build is fully verified."""
    col_left, col_right = st.columns([1.4, 1.0], gap="large")

    with col_left:
        st.markdown(
            f"""
            <div style="padding-top: 1rem;">
              <div class="nova-hero-sub" style="color:var(--accent-emerald);">VERIFICATION CONFIRMED</div>
              <div class="nova-hero-huge" style="color:#ffffff;">
                BUILT.<br>
                VERIFIED.<br>
                <span style="color:var(--accent-emerald);">READY.</span>
              </div>

              <div style="font-family:var(--font-display);font-size:1.8rem;font-weight:700;color:#f8fafc;margin-bottom:0.8rem;">
                {state.project_name}
              </div>

              <div style="font-family:var(--font-mono);font-size:0.85rem;color:var(--text-muted);margin-bottom:2rem;line-height:1.8;">
                <b style="color:#ffffff;">{state.actual_duration_str or state.formatted_elapsed}</b> ACTUAL BUILD TIME &nbsp;•&nbsp;
                {state.estimated_duration_str} ESTIMATE &nbsp;•&nbsp;
                <span style="color:var(--accent-emerald);">ALL 6 GATES VERIFIED</span>
                {f"<br>Runtime: <code>{state.runtime_url}</code> &nbsp;|&nbsp; PID {state.runtime_pid}" if state.runtime_url else ""}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_act1, col_act2 = st.columns([1.5, 1.2])
        with col_act1:
            if state.runtime_url:
                st.markdown(
                    f"""
                    <a href="{state.runtime_url}" target="_blank" style="text-decoration:none;">
                      <button style="width:100%;background:linear-gradient(135deg,#10b981,#059669);border:1px solid rgba(167,243,208,0.4);color:#ffffff;font-family:var(--font-mono);font-size:0.85rem;font-weight:700;letter-spacing:0.12em;padding:0.75rem 1.4rem;border-radius:8px;cursor:pointer;box-shadow:0 0 30px rgba(16,185,129,0.35);">
                        ↗ OPEN PROJECT ({state.runtime_url})
                      </button>
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
        with col_act2:
            if st.button("EXPLORE WORKSPACE", key="btn_succ_explore", use_container_width=True):
                st.session_state["active_drawer"] = "Workspace"
                st.rerun()

    with col_right:
        canvas_html = get_state_canvas_html("SUCCESS", height=460)
        _render_canvas(canvas_html, height=460)


def render_failure_view(state: ProjectState) -> None:
    """Renders the restrained interruption screen when a pipeline stage or runtime halts."""
    col_left, col_right = st.columns([1.1, 1.3], gap="large")

    classification = state.failure_classification or "EXECUTION_FAILURE"
    reason = state.failure_reason or "Verification check did not satisfy prerequisite conditions."

    is_interrupted = state.failure_classification in ("EXECUTION_INTERRUPTED", "SERVER_RESTARTED_MID_BUILD", "USER_CANCELLED")
    sub_title = "PIPELINE INTERRUPT" if is_interrupted else "PIPELINE FAILURE"
    main_title = "INTERRUPTED." if is_interrupted else "FAILED."

    with col_left:
        st.markdown(
            f"""
            <div style="padding-top: 1rem;">
              <div class="nova-hero-sub" style="color:var(--accent-rose);">{sub_title}</div>
              <div class="nova-hero-huge" style="color:#ffffff;">
                BUILD<br>
                <span style="color:var(--accent-rose);">{main_title}</span>
              </div>

              <div style="font-family:var(--font-mono);font-size:1.1rem;font-weight:600;color:#fca5a5;margin-bottom:0.6rem;">
                {classification}
              </div>

              <div style="font-family:var(--font-mono);font-size:0.85rem;color:var(--text-muted);margin-bottom:1.8rem;max-width:540px;line-height:1.6;">
                {reason}
                <br><br>
                Recovery attempts: <b style="color:#ffffff;">{state.recovery_attempts} / 3</b>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("VIEW DIAGNOSTICS & RECOVERY", key="btn_fail_diag", type="primary"):
            st.session_state["active_drawer"] = "Diagnostics"
            st.rerun()

    with col_right:
        canvas_html = get_state_canvas_html("DEBUGGING", height=460)
        _render_canvas(canvas_html, height=460)


def render_side_panels(
    active_drawer: Optional[str],
    state: ProjectState,
    workspace: WorkspaceManager,
    process_manager: ProcessManager,
    runner: ProjectRunner,
    history_manager: HistoryManager,
) -> None:
    """Renders progressive disclosure drawers (Projects, Workspace, Activity, Runtime, Diagnostics)."""
    if not active_drawer:
        return

    st.markdown('<div class="nova-drawer-container">', unsafe_allow_html=True)

    col_head_title, col_head_close = st.columns([5, 1])
    with col_head_title:
        st.markdown(f'<div class="nova-drawer-title">{active_drawer}</div>', unsafe_allow_html=True)
    with col_head_close:
        if st.button("✕ CLOSE", key="close_drawer_btn", use_container_width=True):
            st.session_state["active_drawer"] = None
            st.rerun()

    # 1. PROJECTS DRAWER
    if active_drawer == "Projects":
        records = history_manager.get_recent_projects(15)
        if not records:
            st.markdown("<div style='color:var(--text-muted);font-family:var(--font-mono);'>No project history recorded yet.</div>", unsafe_allow_html=True)
        else:
            for rec in records:
                status_color = "var(--accent-emerald)" if rec.status == "COMPLETED" else "var(--accent-rose)"
                st.markdown(
                    f"""
                    <div class="nova-history-row">
                      <div>
                        <div class="nova-history-name">{rec.project_name}</div>
                        <div class="nova-history-meta">{rec.tech_stack} &nbsp;•&nbsp; {rec.goal[:70]}...</div>
                      </div>
                      <div class="nova-history-right">
                        <div style="color:{status_color};font-weight:700;">{rec.status}</div>
                        <div class="nova-history-meta">{rec.actual_duration_str} &nbsp;({rec.estimate_range}) &nbsp;•&nbsp; {rec.timestamp}</div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # 2. WORKSPACE DRAWER
    elif active_drawer == "Workspace":
        files_dict = workspace.load_all_files()
        if not files_dict:
            st.markdown("<div style='color:var(--text-muted);font-family:var(--font-mono);'>Workspace is empty. Build a project to generate files.</div>", unsafe_allow_html=True)
        else:
            file_names = list(files_dict.keys())
            col_sel, col_down = st.columns([3, 1])
            with col_sel:
                selected_file = st.selectbox("Select File", options=file_names, label_visibility="collapsed")
            with col_down:
                if selected_file:
                    st.download_button(
                        label=f"Download {Path(selected_file).name}",
                        data=files_dict[selected_file],
                        file_name=Path(selected_file).name,
                        mime="text/plain",
                        use_container_width=True,
                    )

            if selected_file:
                content = files_dict[selected_file]
                ext = Path(selected_file).suffix.lstrip(".")
                lang_map = {
                    "py": "python", "js": "javascript", "ts": "typescript", "tsx": "typescript",
                    "jsx": "javascript", "html": "html", "css": "css", "json": "json", "md": "markdown"
                }
                st.code(content, language=lang_map.get(ext, "text"))

    # 3. ACTIVITY DRAWER
    elif active_drawer == "Activity":
        feed = state.activity_feed
        if not feed:
            st.markdown("<div style='color:var(--text-muted);font-family:var(--font-mono);'>No activities recorded yet.</div>", unsafe_allow_html=True)
        else:
            feed_html = []
            for item in reversed(feed):
                color = "#34d399" if item.level == "ok" else "#f87171" if item.level == "bad" else "#a5b4fc"
                feed_html.append(
                    f"""
                    <div style="font-family:var(--font-mono);font-size:0.8rem;padding:0.4rem 0;border-bottom:1px solid rgba(255,255,255,0.03);">
                      <span style="color:#64748b;">[{item.timestamp}]</span> &nbsp;
                      <span style="color:{color};">{item.message}</span>
                    </div>
                    """
                )
            st.markdown(f'<div style="max-height:450px;overflow-y:auto;">{"".join(feed_html)}</div>', unsafe_allow_html=True)

    # 4. RUNTIME DRAWER
    elif active_drawer == "Runtime":
        col_r_info, col_r_ctrl = st.columns([3, 1])
        with col_r_info:
            pid_val = getattr(state, "runtime_pid", None)
            st.markdown(
                f"""
                <div style="font-family:var(--font-mono);font-size:0.85rem;color:#cbd5e1;line-height:1.8;margin-bottom:1rem;">
                  Status: <b style="color:var(--accent-emerald);">{state.runtime_status}</b> &nbsp;|&nbsp;
                  Framework: <b style="color:#ffffff;">{state.project_type}</b><br>
                  Command: <code>{state.runtime_command or 'None'}</code><br>
                  Port: <b style="color:var(--accent-violet);">{state.runtime_port or 'N/A'}</b> &nbsp;|&nbsp;
                  PID: <b>{pid_val or 'N/A'}</b> &nbsp;|&nbsp;
                  URL: <a href="{state.runtime_url}" target="_blank" style="color:var(--accent-violet);">{state.runtime_url or 'N/A'}</a>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_r_ctrl:
            if st.button("RESTART RUNTIME", key="drawer_restart_btn", use_container_width=True):
                runner.restart(state)
                st.rerun()
            if st.button("STOP RUNTIME", key="drawer_stop_btn", use_container_width=True):
                runner.stop(state)
                st.rerun()

        # Terminal logs
        logs = process_manager.get_logs_text()
        st.markdown(f'<div class="nova-terminal">{logs if logs else "Awaiting process launch logs..."}</div>', unsafe_allow_html=True)

    # 5. DIAGNOSTICS DRAWER
    elif active_drawer == "Diagnostics":
        classification = state.failure_classification or "SYSTEM_NORMAL"
        reason = state.failure_reason or "All verification gates passing."
        st.markdown(
            f"""
            <div style="font-family:var(--font-mono);font-size:0.85rem;color:#cbd5e1;line-height:1.8;">
              <div style="font-weight:700;color:var(--accent-rose);margin-bottom:0.5rem;">DIAGNOSTIC CLASSIFICATION: {classification}</div>
              <div style="background:rgba(244,63,94,0.08);border:1px solid rgba(244,63,94,0.25);border-radius:8px;padding:1rem;color:#fca5a5;margin-bottom:1rem;">
                {reason}
              </div>
              <div style="color:var(--text-muted);">Recovery status: {state.recovery_attempts} / 3 automated recovery cycles executed.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # AI Provider & Model Routing Diagnostics
        try:
            from backend.core.llm.model_router import get_model_router
            router = get_model_router()
            diagnostics = router.get_diagnostics()

            st.markdown("<div style='font-family:var(--font-display);font-size:1.1rem;font-weight:700;color:#ffffff;margin-top:1.6rem;margin-bottom:0.8rem;'>AI PROVIDER & MODEL ROUTING TELEMETRY</div>", unsafe_allow_html=True)
            for diag in diagnostics:
                status_color = "var(--accent-emerald)" if diag["status"] == "READY" else ("var(--accent-rose)" if diag["status"] == "ERROR" else "var(--text-faint)")
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:0.65rem 0;border-bottom:1px solid rgba(255,255,255,0.04);font-family:var(--font-mono);font-size:0.8rem;">
                      <div>
                        <b style="color:#ffffff;">{diag['provider']}</b> &nbsp;•&nbsp;
                        <span style="color:var(--accent-violet);">{diag['model']}</span> &nbsp;•&nbsp;
                        <span style="color:var(--text-muted);">Role: {diag['role']}</span>
                      </div>
                      <div style="text-align:right;">
                        <span style="color:{status_color};font-weight:700;">● {diag['status']}</span> &nbsp;|&nbsp;
                        <span style="color:var(--text-muted);">Reqs: {diag['request_count']}</span> &nbsp;|&nbsp;
                        <span style="color:var(--text-muted);">Avg: {diag['avg_latency_ms']}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        except Exception:
            pass

    st.markdown("</div>", unsafe_allow_html=True)
