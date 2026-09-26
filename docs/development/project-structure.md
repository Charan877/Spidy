# SPIDY Project Structure & Directory Layout

This document details the codebase organization, role boundaries, and file locations for SPIDY.

---

## 1. Directory Tree

```
spidy/
├── backend/                  # Authoritative Python backend application
│   ├── agents/               # Multi-agent implementations
│   │   ├── base_agent.py     # Base agent abstractions
│   │   ├── planner_agent.py  # Task graph decomposition & stack detection
│   │   ├── architect_agent.py# System structure and API designs
│   │   ├── developer_agent.py# Code generation and repair
│   │   └── reviewer_agent.py # Quality validation, asset check & gatekeeper
│   ├── core/                 # Shared domain logic and orchestrator utilities
│   │   ├── active_context.py # Active project context isolation
│   │   ├── agent_result.py   # Agent execution result container
│   │   ├── architecture_contract.py # Full-stack architecture definitions
│   │   ├── architecture_validator.py# Structural architecture validator
│   │   ├── artifact_validator.py    # Non-empty file & asset integrity validator
│   │   ├── brand.py          # Central brand identity and naming
│   │   ├── estimation.py     # Duration & complexity estimators
│   │   ├── events.py         # Activity and timeline event models
│   │   ├── history_manager.py# Legacy snapshot cache manager
│   │   ├── llm/              # LLM routing and resilient client integrations
│   │   │   ├── model_router.py      # Multi-provider failover routing
│   │   │   ├── nvidia_client.py     # NVIDIA NIM integration
│   │   │   └── openrouter_client.py # OpenRouter integration
│   │   ├── project_state.py  # State models, task status, events
│   │   ├── task_classifier.py# Request intent classification (new vs follow-up)
│   │   └── workspace_manager.py     # Sandboxed workspace manager
│   ├── database/             # Authoritative SQLite persistence layer
│   │   ├── connection.py     # Database connection factory with WAL mode
│   │   ├── database_manager.py# High-level repository API
│   │   └── schema.py         # Versioned schema migrations (v1, v2)
│   ├── orchestration/        # Orchestrator & state machines
│   │   ├── completion_state_machine.py # Deterministic build lifecycle
│   │   └── orchestrator.py   # End-to-end pipeline coordination
│   ├── runtime/              # Process and environment management
│   │   ├── environment_detector.py # Port discovery and stack detection
│   │   ├── preview_manager.py# HTTP probe and iframe live verification
│   │   ├── process_manager.py# Subprocess tracking and socket binding
│   │   ├── project_runner.py # Build runner and auto-recovery
│   │   └── runtime_session.py# Isolated runtime session dataclass
│   └── ui/                   # Streamlit fallback UI components
│       ├── components.py
│       └── styles.py
├── frontend/                 # Authoritative React 18 + Three.js application
│   ├── public/               # Static assets
│   ├── src/
│   │   ├── components/       # UI panels, HUD, and drawers
│   │   │   ├── ActiveBuildHUD.tsx
│   │   │   ├── Drawers.tsx
│   │   │   ├── FailureView.tsx
│   │   │   ├── HeroCommandPanel.tsx
│   │   │   ├── Navigation.tsx
│   │   │   ├── ProjectsDrawerContent.tsx
│   │   │   ├── ScrollStoryOverlay.tsx
│   │   │   └── SuccessView.tsx
│   │   ├── three/            # 3D cinematic canvas, monument, shaders
│   │   │   ├── AgentConstellation.tsx
│   │   │   ├── CentralCore.tsx
│   │   │   ├── CinematicCamera.tsx
│   │   │   ├── ComputationalMachine.tsx
│   │   │   ├── DataStreams.tsx
│   │   │   ├── FallbackCanvas.tsx
│   │   │   └── World3D.tsx
│   │   ├── types/            # TypeScript interfaces and state models
│   │   ├── App.tsx           # Primary application root
│   │   ├── main.tsx          # Application entrypoint
│   │   └── index.css         # Styling and design system
│   ├── package.json          # Frontend dependencies
│   └── vite.config.ts        # Vite configuration
├── data/                     # Local data storage
│   ├── .gitkeep              # Preserves directory in git
│   └── spidy.db              # Persistent SQLite database (ignored in git)
├── docs/                     # Architecture, development, and testing guides
│   ├── architecture/         # System design and specifications
│   ├── assets/               # Screenshots and visual media (spidy-interface.png)
│   ├── development/          # Setup, workflow, and structure docs
│   └── testing/              # Test strategy and test execution guides
├── scripts/                  # Convenience startup scripts (run.bat, run.ps1)
├── tests/                    # Authoritative automated test suite
│   ├── integration/          # API, persistence, resume, and e2e tests
│   └── unit/                 # Agent, router, state machine, and context tests
├── workspace/                # Sandboxed project workspaces (workspace/<project_id>/)
│   └── .gitkeep              # Preserves directory in git
├── app.py                    # Dual launcher (Starlette server / Streamlit fallback)
├── server.py                 # Primary backend server entrypoint
├── requirements.txt          # Python package requirements
├── CONTRIBUTING.md           # Contribution guidelines and quick checklist
├── LICENSE                   # Apache 2.0 open-source license
├── .env.example              # Environment variable template
├── .gitignore                # Comprehensive Git exclusion rules
└── README.md                 # Project overview and documentation

```

---

## 2. Key Architectural Invariants

1. **One Authoritative Database**: All persistence operations pass through `backend.database.database_manager.DatabaseManager` connected to `data/spidy.db`.
2. **Workspace Sandboxing**: Every generated project lives in an isolated subdirectory `workspace/<project_id>/`. Never write project files to the root workspace.
3. **Port Isolation**: Target application runtimes use ephemeral ports (9000–65535). Control server ports (`8500-8502`) are strictly reserved.
4. **Frozen Visuals**: Three.js shaders, monument geometry, lighting, and camera configurations in `frontend/src/three/` are frozen and protected against regression.

