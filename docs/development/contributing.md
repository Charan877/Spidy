# Contributing to SPIDY

This guide provides guidelines and development workflows for contributing to SPIDY.

---

## 1. Prerequisites

- **Python**: 3.10+ (tested on Python 3.11 and 3.14)
- **Node.js**: 18+ (tested on Node.js 20+)
- **Operating System**: Windows / Linux / macOS

---

## 2. Environment Setup

### 2.1 Backend Setup
1. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   Copy `.env.example` to `.env` and configure your API keys:
   ```bash
   cp .env.example .env
   ```
   Provide valid keys for `NVIDIA_API_KEY` (primary) and/or `OPENROUTER_API_KEY` (fallback).

### 2.2 Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```
2. Build the production assets:
   ```bash
   npm run build
   ```

---

## 3. Running SPIDY

To launch the unified server on port 8501:
```bash
python server.py
```
Open your browser to: `http://localhost:8501`

---

## 4. Development Workflow

1. **Keep Agent Boundaries Clean**:
   - Each agent in `backend/agents/` must focus strictly on its designated responsibility (e.g. Planning, Architecture, Development, or Review).
   - Use `backend/core/active_context.py` to preserve cross-project isolation.

2. **Persistence Integrity**:
   - Database migrations must be added to `backend/database/schema.py` under the versioned migration framework.
   - Always run integration tests when touching the persistence layer.

3. **Frontend Changes**:
   - Do NOT modify the Three.js 3D canvas or shader atmosphere unless specifically requested.
   - Always rebuild frontend assets (`npm run build`) before committing.

4. **Testing Before Committing**:
   - Run the full test suite:
     ```bash
     pytest tests
     ```
   - Ensure all 115 unit and integration tests pass.

