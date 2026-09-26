# SPIDY System Architecture Overview

SPIDY is an autonomous software engineering platform designed to conceptualize, plan, architect, implement, execute, verify, and iteratively evolve full-stack applications through a multi-agent pipeline.

---

## 1. High-Level Architecture

SPIDY operates via an asynchronous, event-driven architecture combining a Python Starlette/Uvicorn backend, a reactive SQLite persistence layer, and a cinematic React 18 + Three.js frontend.

```mermaid
flowchart TD
    User([User Prompt / Conversational Iteration]) --> Server[Starlette / Uvicorn Server (Port 8501)]
    Server --> ActiveCtx[ActiveProjectContext]
    Server --> DB[(SQLite Database: data/spidy.db)]
    Server --> Orch[Conversational Orchestrator]

    subgraph AgentPipeline [Autonomous Multi-Agent Pipeline]
        Orch --> Planner[Planner Agent]
        Planner --> Architect[Architect Agent]
        Architect --> Developer[Developer Agent]
        Developer --> Reviewer[Reviewer Agent]
    end

    subgraph RuntimeSystem [Runtime & Verification]
        Reviewer --> Runtime[Project Runner & Process Manager]
        Runtime --> SocketCheck[Socket Ownership & Port Detection]
        Runtime --> PreviewMgr[Preview & Verification Manager]
    end

    subgraph WorkspaceLayer [Isolated Workspaces]
        Developer --> WS[workspace/proj_<id>/]
        Runtime --> WS
    end

    Runtime --> StateMachine[Completion State Machine]
    StateMachine --> Server
    Server --> WSStream[WebSocket Stream & Event Emitter]
    WSStream --> UI[Frontend 3D UI & Workspace History]
```

---

## 2. Core Subsystems

### 2.1 Project Context Isolation (`backend/core/active_context.py`)
To prevent cross-project contamination across sequential runs (e.g., LeetCode merge algorithms leaking into TaskFlow full-stack apps):
- **`ActiveProjectContext`** tracks the active `project_id`, `build_id`, requirement text, and project workspace.
- **`TaskClassifier`** strictly distinguishes between fresh project creation and conversational follow-up/iterations.
- **`ProjectState`** scopes task graphs and verification checks to the specific `build_id`.
- **`validate_plan_against_requirement`** ensures generated task graphs align with user specifications before code generation begins.

### 2.2 Multi-Agent Pipeline (`backend/agents/`)
1. **Planner Agent (`planner_agent.py`)**: Analyzes requirements, detects frontend/backend stack dependencies, generates ordered execution tasks with prerequisites.
2. **Architect Agent (`architect_agent.py`)**: Defines file structure, component trees, API specifications, and shared schema contracts.
3. **Developer Agent (`developer_agent.py`)**: Generates production code files with multi-layer recovery and fallback repair strategies.
4. **Reviewer Agent (`reviewer_agent.py`)**: Inspects output against architectural specifications and build gates; verifies completion prerequisites.

### 2.3 Runtime & Verification Engine (`backend/runtime/`)
- **Process Manager (`process_manager.py`)**: Manages non-blocking subprocesses, continuous log streaming, and process group lifecycle.
- **Port Detection & Isolation (`environment_detector.py`)**: Dynamically allocates ephemeral ports (9000+), isolating them from control server ports (`8500-8502`).
- **Preview & Verification Manager (`preview_manager.py`, `project_runner.py`)**: Probes live HTTP endpoints, performs automated repairs for missing entrypoints or Vite configurations, and confirms operational status before reporting success.
- **Deterministic 6-Gate Validation Matrix**:
  1. *Specification Alignment*: Validates plan and task graph against requirement before code generation.
  2. *Structural Completeness*: Verifies all files and directories declared in the architecture contract exist on disk.
  3. *Syntax & AST Parsing*: Validates Python AST and JS/TS syntax across all synthesized files.
  4. *Runtime & Socket Health*: Confirms spawned subprocesses bound cleanly to dynamic ports and HTTP endpoints respond.
  5. *Asset & Content Integrity*: Ensures files, templates, and READMEs are non-empty and uncorrupted.
  6. *Reviewer Agent Verification*: Automated gatekeeper audit enforcing build invariants.


### 2.4 Persistence Layer (`backend/database/`)
- **Engine**: SQLite with Write-Ahead Logging (`WAL` mode), foreign keys enabled, and automatic startup recovery reconciliation.
- **Schema**: Versioned migration framework (`schema.py`, current version: 2) managing:
  - `projects`: High-level project metadata, workspace paths, and lifecycle statuses.
  - `builds`: Detailed build records, elapsed durations, task metrics, and estimated complexity.
  - `agent_runs`: Discrete execution records per agent per build.
  - `activity`: Granular timeline events and audit log stream.
  - `runtime_sessions`: Isolated execution runtimes, process PIDs, and port bindings.
  - `verification`: Deterministic multi-gate validation records.
  - `messages`: Conversational interaction history and user prompts per project.

### 2.5 Model Router (`backend/core/llm/model_router.py`)
- Provides resilient LLM routing across multiple providers (NVIDIA NIM and OpenRouter).
- Supports automatic fallbacks, rate-limit backoff, and model specialization for planning, coding, and reviewing.

