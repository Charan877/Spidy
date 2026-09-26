# Contributing to SPIDY

Thank you for your interest in contributing to **SPIDY**! We welcome bug reports, documentation improvements, architectural proposals, and code contributions.

---

## Code of Conduct & Development Guidelines

Before submitting contributions, please review our comprehensive guides:

- **[Contributing Guide](docs/development/contributing.md)**: Development setup, coding guidelines, and workflow.
- **[System Architecture](docs/architecture/overview.md)**: Architectural subsystems, multi-agent contracts, and state machine invariants.
- **[Project Structure](docs/development/project-structure.md)**: Codebase layout and role boundaries.
- **[Testing Strategy](docs/testing/strategy.md)**: Running the test suite and adding unit/integration tests.

---

## Quick Contribution Checklist

1. **Clean Agent Boundaries**: Maintain single-responsibility boundaries for agents in `backend/agents/`.
2. **Persistence Integrity**: Never execute raw destructive queries against `data/spidy.db`; add idempotent migrations to `backend/database/schema.py`.
3. **Workspace Isolation**: Generated projects must always remain isolated under `workspace/<project_id>/`.
4. **Secret Quarantine**: Never commit API keys, `.env` files, or local database state.
5. **Full Test Verification**: Ensure all 115 automated tests pass before opening a pull request:
   ```bash
   pytest tests -v
   ```
6. **Frontend Build Verification**: If touching the frontend, verify that the production build succeeds without errors:
   ```bash
   cd frontend
   npm run build
   ```
