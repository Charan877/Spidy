# SPIDY Testing Strategy

This document outlines the testing architecture, suites, and verification procedures for SPIDY.

---

## 1. Test Suite Structure

The test suite is organized into two primary categories under `tests/`:

```
tests/
├── integration/
│   ├── test_conversational_api.py          # REST and state machine transitions
│   ├── test_focusflow_fallback_recovery_e2e.py # Fallback provider & targeted recovery
│   ├── test_platform.py                    # System dependencies, node/npm, git detection
│   ├── test_server_persistence.py          # SQLite database API endpoints and migrations
│   ├── test_server_resume_and_recovery.py  # Interrupted build reconciliation & resume
│   └── test_spendwise_fullstack_architecture_e2e.py # Full-stack architecture & artifact validation
└── unit/
    ├── test_architecture_compliance.py     # Clean architecture & import boundary compliance
    ├── test_architecture_contract.py       # Full-stack contract definitions & validation
    ├── test_completion_state_machine.py    # State machine transitions & invariant enforcement
    ├── test_conversational_orchestrator.py# Multi-turn conversations & project state
    ├── test_database.py                    # SQLite WAL connection, foreign keys, schema migrations
    ├── test_estimation.py                  # Project duration and complexity estimators
    ├── test_fallback_recovery_state_machine.py # Recovery lifecycle & task state transitions
    ├── test_json_parser.py                 # Robust LLM JSON parsing and sanitization
    ├── test_model_router.py                # Multi-provider failover and rate-limiting
    ├── test_pipeline_prerequisites.py       # Task dependency resolution & topological sorting
    ├── test_placeholder_and_readme_validator.py # Non-empty file & placeholder validation
    ├── test_port_detection.py              # Port scanning, process ownership, ephemeral allocation
    ├── test_project_context_isolation_regression.py # Context isolation & cross-project pollution prevention
    ├── test_runtime_recovery.py            # Subprocess crash recovery and port conflict handling
    └── test_taskflow_fullstack_fixes.py    # Full-stack TaskFlow pipeline and recovery validation
```

---

## 2. Running Tests

### 2.1 Complete Test Run
Run the full test suite using `pytest` or Python's standard `unittest`:
```bash
# Recommended with pytest:
pytest tests -v

# Or with unittest:
python -m unittest discover -s tests
```

### 2.2 Running Specific Test Suites
To run only unit tests:
```bash
pytest tests/unit
```

To run only integration tests:
```bash
pytest tests/integration
```

To run a specific test module:
```bash
pytest tests/unit/test_project_context_isolation_regression.py
```


---

## 3. Key Testing Principles

1. **Deterministic Isolation**: Tests must never pollute `data/spidy.db` or create permanent files in user workspaces. Tests use temporary directories (`tempfile.TemporaryDirectory`) or in-memory SQLite fixtures.
2. **Subprocess Safety**: Any test that mocks or spawns processes must terminate them cleanly (`proc.terminate()` / `proc.kill()`) to prevent orphaned port listeners.
3. **No External Network Dependencies in Unit Tests**: External LLM API calls are mocked or verified with timeout protection so tests can run offline and deterministically.
4. **Context Isolation Verification**: Regression tests verify that consecutive project runs never leak task descriptions, task IDs, or architectural artifacts across project boundaries.
