# SPIDY — Autonomous Software Engineering Platform

SPIDY is an autonomous multi-agent software engineering system featuring an immersive, real-time 3D computational interface. It takes high-level user specifications and autonomously plans, architects, writes, runs, verifies, and self-heals full-stack software applications in isolated sandboxes.

```
AI THAT
BUILDS
SOFTWARE.
```

> **Describe what you want to build.** SPIDY decomposes requirements, designs system contracts, synthesizes multi-file codebases, binds live network runtimes, subjects projects to rigorous multi-gate verification, and serves interactive web previews in real time.

---

## Architecture Overview

```mermaid
flowchart TD
    User([User Prompt / Conversational Iteration]) --> Server[SPIDY Control Server (localhost:8501)]
    Server --> ActiveCtx[ActiveProjectContext Isolation]
    Server --> DB[(SQLite Database: data/spidy.db WAL Mode)]
    Server --> Router[ModelRouter: Resilient Failover]
    Router --> NIM[NVIDIA NIM Primary]
    Router --> OR[OpenRouter Fallback]

    Server --> Pipeline[Autonomous Multi-Agent Pipeline]
    subgraph MultiAgentPipeline [Multi-Agent Pipeline]
        Pipeline --> Planner[Planner Agent: Scoping & Stack Detection]
        Planner --> Architect[Architect Agent: Contract Decomposition]
        Architect --> Developer[Developer Agent: Multi-File Synthesis]
        Developer --> Reviewer[Reviewer Agent: Multi-Gate Verification]
    end

    subgraph RuntimeSystem [Runtime & Process Sandbox]
        Developer --> WS[workspace/proj_<id>/]
        Reviewer --> Runtime[Project Runner & Process Manager]
        Runtime --> Ports[Dynamic Port Discovery (9000+)]
        Runtime --> Health[HTTP Probing & Runtime Health Verification]
    end

    Reviewer --> StateMachine[Completion State Machine]
    StateMachine --> Server
    Server --> WSStream[WebSocket Stream & Event Emitter]
    WSStream --> UI[3D Computational Frontend (React 18 + Three.js)]
```

---

## Key Capabilities

- **Autonomous Multi-Agent Pipeline**:
  - **Planner Agent**: Analyzes specifications, detects target application stacks (FastAPI, React/Vite, SQLite, Python CLI, HTML/JS), and constructs topologically sorted task dependency graphs.
  - **Architect Agent**: Generates complete full-stack contracts, file trees, API routes, database schemas, and shared frontend/backend data models before code is generated.
  - **Developer Agent**: Writes production-ready code files with multi-layer recovery, syntax validation, and self-repair capabilities.
  - **Reviewer Agent**: Audits generated applications against architecture specifications, asset integrity rules, and runtime status before certifying a build.
- **Strict 6-Gate Verification Matrix**:
  1. *Specification Alignment Gate*: Validates that planned tasks and architecture match user requirements without cross-project context pollution.
  2. *Structural Architecture Completeness Gate*: Verifies that all required files, directories, and entrypoints declared in the architectural contract exist on disk.
  3. *Syntax & Type Validation Gate*: Runs AST parsers and syntax validators across all generated code.
  4. *Runtime & Process Health Gate*: Spawns target processes, verifies socket binding on dynamically allocated ports, and probes HTTP endpoints.
  5. *Interactive Asset & Integrity Gate*: Ensures all generated source files, stylesheets, and READMEs are non-empty and free of unpopulated templates.
  6. *Reviewer Agent Gate*: Executes automated quality audits and validates deterministic build invariants.
- **Resilient Multi-Provider LLM Routing**:
  - Primary provider: NVIDIA NIM (`z-ai/glm-5.3`, `nvidia/nemotron-3.5`, `google/gemma-4-31b`).
  - Secondary fallback: OpenRouter (`openrouter/free`).
  - Automatic exponential backoff, rate-limit handling, and role-based model specialization.
- **Workspace Sandboxing & Port Isolation**:
  - Every project is confined to its own isolated directory under `workspace/<project_id>/`.
  - Application runtimes dynamically discover available ephemeral ports (`9000–65535`), never colliding with SPIDY's control ports (`8500–8502`).
- **Persistence & Startup Reconciliation**:
  - SQLite database (`data/spidy.db`) operating with Write-Ahead Logging (`WAL` mode) and versioned schema migrations.
  - Startup reconciliation automatically recovers interrupted builds and preserves complete project audit histories.
- **Cinematic 3D Real-Time Interface**:
  - Interactive Three.js canvas featuring a central computational core, live agent constellation, data stream particle fields, and cinematic camera controls.
  - Real-time WebSocket streaming of build telemetry, live activity logs, task graph status, and embedded live application previews.

---

## Quick Start

### Prerequisites
- **Python**: 3.10+ (tested on Python 3.11 and 3.14)
- **Node.js**: 18+ (tested on Node.js 20+)

### 1. Clone & Configure Environment

```bash
# Clone repository
git clone https://github.com/<your-username>/spidy.git
cd spidy

# Set up Python virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

Edit `.env` to configure your API credentials:
```ini
# Primary Provider (NVIDIA NIM)
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=z-ai/glm-5.3

# Resilient Fallback Provider (OpenRouter)
OPENROUTER_API_KEY=sk-or-your-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openrouter/free
```

### 2. Build Frontend Assets

```bash
cd frontend
npm install
npm run build
cd ..
```

### 3. Launch SPIDY

Choose one of the following launch options:

- **Windows Batch Launcher**:
  ```cmd
  run.bat
  ```
- **Direct Python Server**:
  ```bash
  python server.py
  ```
- **Application Launcher**:
  ```bash
  python app.py
  ```

Open your browser to: **`http://localhost:8501`**

---

## REST API & WebSocket Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/diagnostics` | System health, model router status, platform runtime detection |
| `GET` | `/api/state` | Current orchestrator phase, active build state, and telemetry feed |
| `POST` | `/api/build` | Initiate a new autonomous build from a user specification |
| `GET` | `/api/projects` | List all persisted projects with historical build summaries |
| `GET` | `/api/projects/{project_id}` | Detailed project record with build history and metadata |
| `GET` | `/api/builds/{build_id}` | Detailed build record, task timeline, and execution logs |
| `GET` | `/api/history` | Chronological activity and build history stream |
| `POST` | `/api/projects/{project_id}/resume` | Resume an existing project workspace or send follow-up instructions |
| `WS` | `/ws` | Real-time WebSocket connection for live telemetry and activity streaming |

---

## Directory Structure

```
spidy/
├── backend/                  # Authoritative Python backend application
│   ├── agents/               # Multi-agent implementations (Planner, Architect, Dev, Reviewer)
│   ├── core/                 # Active context, architecture contracts, validators, LLM router
│   ├── database/             # SQLite connection factory (WAL mode), migrations, repository API
│   ├── orchestration/        # Conversational orchestrator and deterministic state machine
│   ├── runtime/              # Subprocess manager, port detector, preview manager, session runner
│   └── ui/                   # Streamlit fallback UI components
├── frontend/                 # React 18 + Three.js + Tailwind CSS web interface
│   ├── src/
│   │   ├── components/       # Active HUD, navigation, drawers, command panels
│   │   ├── three/            # 3D cinematic canvas, monument, shaders, camera controller
│   │   └── types/            # TypeScript interfaces and telemetry types
│   ├── package.json
│   └── vite.config.ts
├── data/                     # Local data storage (.gitkeep committed, databases ignored)
│   └── spidy.db              # Embedded SQLite database (WAL mode)
├── docs/                     # Comprehensive technical documentation
│   ├── architecture/         # System design, verification matrix, state machine specs
│   ├── development/          # Project structure, coding standards, contributing guide
│   └── testing/              # Testing strategy, test execution instructions
├── scripts/                  # Convenience startup scripts (run.bat, run.ps1)
├── tests/                    # Automated test suite (114+ unit and integration tests)
│   ├── integration/          # API, persistence, resume, and e2e integration tests
│   └── unit/                 # Agent, router, state machine, and context unit tests
├── workspace/                # Sandboxed project workspaces (workspace/<project_id>/)
├── app.py                    # Dual launcher (Starlette server / Streamlit fallback)
├── server.py                 # Primary backend server entrypoint
├── requirements.txt          # Python dependencies
├── .env.example              # Documented environment variable template
├── .gitignore                # Comprehensive Git exclusion rules
└── README.md                 # Project overview and quickstart guide
```

---

## Testing & Verification

SPIDY includes an extensive test suite of **114+ automated unit and integration tests** covering context isolation, database persistence, state transitions, port detection, and fallback recovery.

```bash
# Run full test suite with pytest:
pytest tests -v

# Run with standard Python unittest:
python -m unittest discover -s tests

# Run only unit tests:
pytest tests/unit

# Run only integration tests:
pytest tests/integration
```

---

## Security & Sandboxing Invariants

- **Secret Quarantine**: Real API keys (`nvapi-...`, `sk-or-...`) are strictly quarantined in `.env` and excluded from version control via `.gitignore`. `.env.example` contains only placeholder values.
- **Workspace Sandboxing**: Every generated target application is strictly confined to `workspace/<project_id>/` to prevent directory contamination.
- **Port Isolation**: Control ports (`8500–8502`) are protected against binding by target applications; target services use ephemeral ports (`9000+`).
- **No External Pollution in Tests**: Automated tests use isolated temporary directories and mock external network dependencies to ensure reproducible, deterministic test runs.

---

## Documentation

- [System Architecture Overview](docs/architecture/overview.md)
- [Project Structure & Directory Layout](docs/development/project-structure.md)
- [Contributing Guidelines](docs/development/contributing.md)
- [Testing Strategy & Test Execution](docs/testing/strategy.md)

---

## License

This project is licensed under the Apache 2.0 License.