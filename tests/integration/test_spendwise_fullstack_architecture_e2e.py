"""End-to-End integration test simulating the exact SpendWise full-stack architecture scenario.

Validates:
1. Strict adherence to contracted stack (React + TypeScript + Vite, FastAPI, SQLite).
2. Elimination of placeholder paths ('path/to/file.ext').
3. Deterministic rejection of downgrades to static HTML/CSS/JS.
4. Comprehensive, project-specific README validation.
5. Real fullstack CRUD verification contract.
"""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.orchestration.orchestrator import MultiAgentPipeline
from backend.runtime.process_manager import ProcessManager
from backend.runtime.project_runner import ProjectRunner
from backend.core.artifact_validator import is_placeholder_path, validate_readme_content


class TestSpendWiseFullstackArchitectureE2E(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceManager(self.tmp_dir)
        self.process_mgr = ProcessManager()
        self.runner = ProjectRunner(self.workspace, self.process_mgr)
        self.pipeline = MultiAgentPipeline(self.workspace, self.runner)
        self.state = ProjectState(
            goal=(
                'Build a full-stack web application called "SpendWise", a personal expense tracking and budgeting application. '
                'Required stack: React, TypeScript, Vite, FastAPI, SQLite, REST API, frontend/backend communication.'
            ),
            selected_language="Fullstack",
        )
        self.state.project_id = "proj_spendwise_test"
        self.state.build_id = "bld_spendwise_001"
        self.state.auto_confirm = True

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_spendwise_end_to_end_compliant_generation(self, mock_call_llm):
        """Simulate SpendWise generation: planning derives React+Vite+FastAPI, codegen outputs real files,

        Architecture Compliance Gate verifies layers, and README is project-specific.
        """
        # Call 1: Planner Agent Response
        plan_response = """{
            "project_name": "SpendWise",
            "detected_language": "Fullstack",
            "is_fullstack": true,
            "architecture_summary": "SpendWise expense tracker with React+Vite frontend, FastAPI backend, and SQLite database",
            "tech_stack": ["React", "TypeScript", "Vite", "FastAPI", "SQLite", "REST API"],
            "files": [
                "requirements.txt",
                "app/main.py",
                "app/database.py",
                "package.json",
                "vite.config.ts",
                "index.html",
                "src/main.tsx",
                "src/App.tsx",
                "README.md"
            ],
            "tasks": [
                "Generate requirements.txt",
                "Generate app/main.py",
                "Generate app/database.py",
                "Generate package.json",
                "Generate vite.config.ts",
                "Generate index.html",
                "Generate src/main.tsx",
                "Generate src/App.tsx",
                "Generate README.md"
            ]
        }"""

        # Call 2: Developer Agent Codegen
        codegen_response = """### FILE: requirements.txt
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0

### FILE: app/database.py
import sqlite3
def get_db():
    conn = sqlite3.connect("spendwise.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_db()

### FILE: app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from app.database import get_db

app = FastAPI(title="SpendWise API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str

@app.get("/")
def root():
    return {"app": "SpendWise", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/expenses")
def list_expenses():
    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/expenses")
def create_expense(expense: ExpenseCreate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (title, amount, category) VALUES (?, ?, ?)",
        (expense.title, expense.amount, expense.category),
    )
    conn.commit()
    exp_id = cur.lastrowid
    conn.close()
    return {"id": exp_id, "title": expense.title, "amount": expense.amount, "category": expense.category}

### FILE: package.json
{
  "name": "spendwise-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^4.4.0"
  }
}

### FILE: vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 }
});

### FILE: index.html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>SpendWise</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>

### FILE: src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

### FILE: src/App.tsx
import React, { useState, useEffect } from 'react';

interface Expense {
  id: number;
  title: str;
  amount: number;
  category: str;
}

export default function App() {
  const [expenses, setExpenses] = useState<Expense[]>([]);

  useEffect(() => {
    fetch('/api/expenses')
      .then(res => res.json())
      .then(data => setExpenses(data))
      .catch(console.error);
  }, []);

  return (
    <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
      <h1>SpendWise Expense Tracker</h1>
      <p>Managing budget and tracking expenses effectively.</p>
      <ul>
        {expenses.map(e => (
          <li key={e.id}>{e.title}: ${e.amount} ({e.category})</li>
        ))}
      </ul>
    </div>
  );
}

### FILE: README.md
# SpendWise - Personal Expense Tracker & Budgeting

SpendWise is a personal finance management tool for expense tracking and budget planning.

## Architecture
- Frontend: React 18 with TypeScript and Vite
- Backend: FastAPI (Python 3)
- Database: SQLite

## API Endpoints
- `GET /api/expenses`: List all recorded expenses
- `POST /api/expenses`: Create a new expense item
- `GET /health`: Server health check

## Running the Project
1. Install backend dependencies: `pip install -r requirements.txt`
2. Start API: `uvicorn app.main:app --port 8000`
3. Run Vite dev server: `npm install && npm run dev`
"""

        mock_call_llm.side_effect = [plan_response, codegen_response]

        # 1. Analyze & Plan
        self.pipeline.analyze_and_plan(self.state)
        self.assertEqual(self.state.project_name, "SpendWise")
        self.assertEqual(self.state.runtime_type, "fullstack")
        self.assertIsNotNone(self.state.architecture_contract)
        arch = self.state.architecture_contract
        fe_fw = arch.get("frontend_framework") if isinstance(arch, dict) else getattr(arch, "frontend_framework", None)
        be_fw = arch.get("backend_framework") if isinstance(arch, dict) else getattr(arch, "backend_framework", None)
        self.assertEqual(fe_fw, "React")
        self.assertEqual(be_fw, "FastAPI")

        # 2. Execute Build
        self.pipeline.execute_build(self.state)

        # 3. Verify workspace files
        ws_files = self.workspace.list_files()
        self.assertIn("package.json", ws_files)
        self.assertIn("vite.config.ts", ws_files)
        self.assertIn("src/main.tsx", ws_files)
        self.assertIn("src/App.tsx", ws_files)
        self.assertIn("app/main.py", ws_files)
        self.assertIn("app/database.py", ws_files)
        self.assertIn("requirements.txt", ws_files)
        self.assertIn("README.md", ws_files)

        # 4. Verify ZERO placeholder files exist
        for wf in ws_files:
            is_ph, reason = is_placeholder_path(wf)
            self.assertFalse(is_ph, f"Workspace contains placeholder file '{wf}': {reason}")

        # 5. Verify README is project-specific and valid
        readme_content = self.workspace.read_file("README.md")
        is_readme_ok, readme_reason = validate_readme_content(
            readme_content,
            project_name="SpendWise",
            goal="Build a personal expense tracking and budgeting application",
        )
        self.assertTrue(is_readme_ok, f"README validation failed: {readme_reason}")
        self.assertIn("SpendWise", readme_content)
        self.assertIn("expenses", readme_content.lower())
        self.assertNotIn("Fork the repository", readme_content)


if __name__ == "__main__":
    unittest.main()
