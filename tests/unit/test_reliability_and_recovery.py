"""Unit tests for SPIDY Autonomous Engineering Reliability & Recovery Hardening.

Validates:
- Failure fingerprinting and normalized signatures
- Failure tracker loop detection
- ProjectState lifecycle transition guards (AWAITING_CONFIRMATION, WAITING_FOR_USER, FAILED->SUCCESS)
- No Fake Recovery / No Fake SUCCESS enforcement
- Evidence-based retry prompting and recovery bounds
- Process crash missing-dependency diagnosis and recovery
"""

import os
import sys
from pathlib import Path
import pytest

from backend.core.failure_fingerprint import (
    FailureFingerprint,
    FailureTracker,
    normalize_error_message,
)
from backend.core.project_state import ProjectState, Task


def test_normalize_error_message():
    """Verify paths, memory addresses, timestamps, and numbers are stripped."""
    err1 = "FileNotFoundError: [WinError 3] The system cannot find the path specified: 'D:\\AI_Coding_Agent\\temp\\app.py' at 0x000001FA98C2"
    err2 = "FileNotFoundError: [WinError 3] The system cannot find the path specified: 'C:\\Users\\test\\app.py' at 0x000002BC44A1"

    norm1 = normalize_error_message(err1)
    norm2 = normalize_error_message(err2)

    assert norm1 == norm2
    assert "hexaddr" in norm1
    assert "000001fa98c2" not in norm1
    assert "ai_coding_agent" not in norm1


def test_failure_fingerprint_deterministic_hash():
    """Verify identical error signatures produce identical hashes."""
    fp1 = FailureFingerprint.create(
        operation="generate_artifact",
        failure_type="VALIDATION_FAILED",
        target="app.py",
        error_message="SyntaxError: invalid syntax at line 42",
        phase="BUILD",
    )
    fp2 = FailureFingerprint.create(
        operation="generate_artifact",
        failure_type="VALIDATION_FAILED",
        target="app.py",
        error_message="SyntaxError: invalid syntax at line 89",
        phase="BUILD",
    )

    assert fp1.fingerprint_hash == fp2.fingerprint_hash
    assert fp1.matches(fp2)


def test_failure_tracker_loop_detection():
    """Verify failure tracker detects loops when the same failure occurs repeatedly."""
    tracker = FailureTracker(loop_threshold=2)

    # First occurrence -> not a loop
    is_loop = tracker.record_failure(
        operation="generate_artifact",
        failure_type="VALIDATION_FAILED",
        target="app.py",
        error_message="SyntaxError: invalid syntax at line 10",
    )
    assert not is_loop
    assert tracker.get_failure_count("generate_artifact", "app.py") == 1

    # Second occurrence -> loop threshold reached
    is_loop2 = tracker.record_failure(
        operation="generate_artifact",
        failure_type="VALIDATION_FAILED",
        target="app.py",
        error_message="SyntaxError: invalid syntax at line 20",
    )
    assert is_loop2
    assert tracker.is_loop_detected

    # Success clears the active failure record and loop detection
    tracker.record_success("generate_artifact", "app.py")
    assert not tracker.is_loop_detected
    assert tracker.get_failure_count("generate_artifact", "app.py", active_only=True) == 0


def test_project_state_rejects_premature_engineering():
    """Verify that engineering cannot start while AWAITING_CONFIRMATION."""
    state = ProjectState(goal="Build a website")
    state.project_state = "AWAITING_CONFIRMATION"

    assert state.is_awaiting_confirmation()
    assert not state.can_execute_engineering()

    # Attempt transition to PLANNING or BUILDING
    res = state.transition_to("PLANNING")
    assert not res
    assert state.project_state == "AWAITING_CONFIRMATION"

    res_build = state.transition_to("BUILDING")
    assert not res_build
    assert state.project_state == "AWAITING_CONFIRMATION"


def test_project_state_waiting_for_user_lifecycle():
    """Verify WAITING_FOR_USER state blocks engineering until explicit release."""
    state = ProjectState(goal="Complex architecture")
    state.wait_for_user("Please clarify database engine choice")

    assert state.project_state == "WAITING_FOR_USER"
    assert state.waiting_for_user_reason == "Please clarify database engine choice"
    assert not state.can_execute_engineering()

    # Direct transition to engineering must be rejected
    res = state.transition_to("PLANNING")
    assert not res
    assert state.project_state == "WAITING_FOR_USER"

    # Explicit release unblocks engineering
    released = state.release_from_user("ENGINEERING_READY")
    assert released
    assert state.project_state == "ENGINEERING_READY"
    assert state.can_execute_engineering()


def test_project_state_prohibits_failed_to_success():
    """Verify state machine strictly forbids direct FAILED -> SUCCESS transitions."""
    state = ProjectState(goal="Test app")
    state.project_state = "FAILED"
    state.failure_reason = "Compile error in main.py"

    # Illegal jump to SUCCESS
    res = state.transition_to("SUCCESS")
    assert not res
    assert state.project_state == "FAILED"


def test_project_state_prohibits_success_with_failed_required_tasks():
    """Verify state machine strictly forbids SUCCESS if any required task is FAILED."""
    state = ProjectState(goal="Test app")
    state.project_state = "VERIFYING"
    state.is_project_generated = True

    state.add_task(
        task_id="t-1",
        title="Build backend",
        phase="BUILD",
        is_required=True,
    )
    state.fail_task("t-1", "Syntax error in server.py")

    assert state.has_failed_required_tasks()

    # Attempt to transition to SUCCESS
    res = state.transition_to("SUCCESS")
    assert not res
    assert state.project_state != "SUCCESS"


def test_project_state_failure_tracking_integration():
    """Verify ProjectState seamlessly delegates failure recording to FailureTracker."""
    state = ProjectState(goal="Web app")

    # Record first failure
    loop1 = state.record_failure(
        operation="compile",
        failure_type="SYNTAX_ERROR",
        target="script.js",
        error_message="Unexpected token < at 12:4",
    )
    assert not loop1

    # Record second identical failure
    loop2 = state.record_failure(
        operation="compile",
        failure_type="SYNTAX_ERROR",
        target="script.js",
        error_message="Unexpected token < at 18:9",
    )
    assert loop2

    # Verify serialization includes loop state
    state_dict = state.to_dict()
    assert state_dict["failure_loop_detected"] is True


def test_project_state_prohibits_success_when_failure_reason_exists():
    """Verify transition to SUCCESS is rejected if an active failure reason exists."""
    state = ProjectState(goal="Web app")
    state.project_state = "VERIFYING"
    state.is_project_generated = True
    state.failure_reason = "Unresolved database connection timeout"

    res = state.transition_to("SUCCESS")
    assert not res
    assert state.project_state != "SUCCESS"


def test_reviewer_recovery_terminates_on_repeated_identical_issues():
    """Verify reviewer recovery loop breaks when identical issues repeat consecutively."""
    state = ProjectState(goal="Portfolio site")
    issues = ["Missing navigation links", "Asset image.png not found"]
    issues_str = "; ".join(issues)

    # First attempt: recorded, not a loop
    is_loop_1 = state.record_failure("reviewer_audit", "NEEDS_RECOVERY", "workspace", issues_str, phase="REVIEW")
    assert not is_loop_1

    # Second attempt with identical issues: detected as loop
    is_loop_2 = state.record_failure("reviewer_audit", "NEEDS_RECOVERY", "workspace", issues_str, phase="REVIEW")
    assert is_loop_2


def test_missing_dependency_diagnosis_regex():
    """Verify regex accurately extracts missing package names from python tracebacks."""
    import re

    sample_stderr_1 = "Traceback (most recent call last):\n  File 'app.py', line 1, in <module>\nModuleNotFoundError: No module named 'fastapi'"
    sample_stderr_2 = "ImportError: No module named 'uvicorn.main'"

    match1 = re.search(r"(?:No module named|ModuleNotFoundError: No module named)\s+['\"]([^'\"]+)['\"]", sample_stderr_1)
    assert match1 is not None
    assert match1.group(1).split(".")[0] == "fastapi"

    match2 = re.search(r"(?:No module named|ModuleNotFoundError: No module named)\s+['\"]([^'\"]+)['\"]", sample_stderr_2)
    assert match2 is not None
    assert match2.group(1).split(".")[0] == "uvicorn"


def test_runtime_session_terminate_guard_system_pids(monkeypatch):
    """Verify RuntimeSession.terminate never calls taskkill on system PIDs <= 4."""
    from backend.runtime.runtime_session import RuntimeSession
    import subprocess

    session = RuntimeSession()
    # Mock a dummy process with PID = 4 (System)
    class DummyProc:
        pid = 4
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=3): pass
        def kill(self): pass

    session.process = DummyProc()

    called_taskkill = []
    def mock_run(cmd, **kwargs):
        called_taskkill.append(cmd)

    monkeypatch.setattr(subprocess, "run", mock_run)

    session.terminate()
    # Taskkill must NOT have been called for PID 4
    assert len(called_taskkill) == 0
