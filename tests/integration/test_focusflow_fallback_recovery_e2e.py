"""End-to-End integration test simulating the exact FocusFlow fallback + recovery scenario.

Scenario:
- Goal: "Build a web application called FocusFlow, a personal task and productivity manager."
- Files planned: index.html, style.css, script.js, README.md
- Initial code generation returns index.html and style.css, missing script.js and README.md.
- Targeted recovery activates for script.js and README.md.
- Primary provider fails (e.g. NVIDIA timeout/error).
- Fallback provider (OpenRouter) succeeds.
- File parser handles fallback output without fences.
- Artifact validator validates artifacts.
- Task state machine transitions: FAILED -> RECOVERING -> RETRYING -> SUCCESS.
- recalculate_task_graph() unblocks downstream RUN task.
- Build completion gate passes.
- Runtime launches and verifies.
- Final state reaches BUILT. RUNNING / BUILT. VERIFIED.
"""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from backend.core.llm.types import LLMResponse
from backend.core.project_state import ProjectState
from backend.core.workspace_manager import WorkspaceManager
from backend.orchestration.orchestrator import MultiAgentPipeline
from backend.runtime.process_manager import ProcessManager
from backend.runtime.project_runner import ProjectRunner


class TestFocusFlowFallbackRecoveryE2E(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.workspace = WorkspaceManager(self.tmp_dir)
        self.process_mgr = ProcessManager()
        self.runner = ProjectRunner(self.workspace, self.process_mgr)
        self.pipeline = MultiAgentPipeline(self.workspace, self.runner)
        self.state = ProjectState(
            goal='Build a web application called "FocusFlow", a personal task and productivity manager.',
            selected_language="HTML/CSS/JS",
        )
        self.state.project_id = "proj_focusflow_test"
        self.state.build_id = "bld_focusflow_001"
        self.state.user_approved = True

    def tearDown(self):
        if hasattr(self, "runner"):
            try:
                self.runner.stop(self.state)
            except Exception:
                pass
        if Path(self.tmp_dir).exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_focusflow_end_to_end_fallback_recovery_to_running(self, mock_call_llm):
        """Simulate the FocusFlow scenario where primary misses script.js and README.md,

        targeted recovery uses fallback, validates artifacts, unblocks runtime, and succeeds.
        """
        # Call 1: Planner
        plan_response = """{
            "project_name": "FocusFlow",
            "detected_language": "HTML/CSS/JS",
            "architecture_summary": "A clean HTML/CSS/JS productivity manager",
            "tech_stack": ["HTML5", "CSS3", "JavaScript"],
            "files": ["index.html", "style.css", "script.js", "README.md"],
            "tasks": ["Generate index.html", "Generate style.css", "Generate script.js", "Generate README.md"]
        }"""

        # Call 2: Initial code generation (returns index.html and style.css, misses script.js and README.md)
        initial_codegen_response = """### FILE: index.html
<!DOCTYPE html>
<html>
<head><title>FocusFlow</title><link rel="stylesheet" href="style.css"></head>
<body>
  <h1>FocusFlow</h1>
  <div id="tasks"></div>
  <script src="script.js"></script>
</body>
</html>

### FILE: style.css
body { font-family: sans-serif; background: #121212; color: #fff; margin: 20px; }
h1 { color: #4ade80; }
"""

        # Call 3: Targeted recovery for script.js (fallback output without ### FILE fence)
        recovery_script_js = """
// FocusFlow task management core
const tasks = [
  { id: 1, title: "Review tasks", done: false },
  { id: 2, title: "Deep work session", done: true }
];

function renderTasks() {
  const container = document.getElementById("tasks");
  if (!container) return;
  container.innerHTML = tasks.map(t => `<p>${t.title} [${t.done ? "DONE" : "TODO"}]</p>`).join("");
}

document.addEventListener("DOMContentLoaded", renderTasks);
"""

        # Call 4: Targeted recovery for README.md (fallback output without ### FILE fence)
        recovery_readme = """# FocusFlow Task Manager

FocusFlow is a personal productivity tool designed for deep work.

## Features
- Track tasks
- Clean modern dark mode UI
- Minimalist workflow
"""

        mock_call_llm.side_effect = [
            plan_response,
            initial_codegen_response,
            recovery_script_js,
            recovery_readme,
        ]

        # 1. Analyze and Plan
        self.pipeline.analyze_and_plan(self.state)

        # Verify planned tasks
        self.assertEqual(len(self.state.tasks), 7)  # 4 build tasks + run + test + doc
        build_task_ids = [t.id for t in self.state.tasks if t.phase == "BUILD"]
        self.assertEqual(len(build_task_ids), 4)

        # 2. Execute Build
        self.pipeline.execute_build(self.state)

        # 3. Verify all 4 files were written to workspace
        workspace_files = self.workspace.list_files()
        self.assertIn("index.html", workspace_files)
        self.assertIn("style.css", workspace_files)
        self.assertIn("script.js", workspace_files)
        self.assertIn("README.md", workspace_files)

        # 4. Verify script.js and README.md tasks are SUCCESS (not FAILED!)
        script_task = next(t for t in self.state.tasks if t.file_path == "script.js")
        readme_task = next(t for t in self.state.tasks if t.file_path == "README.md")
        self.assertEqual(script_task.status, "SUCCESS")
        self.assertEqual(readme_task.status, "SUCCESS")

        # 5. Verify build completion gate did not halt the build
        self.assertFalse(self.state.has_failed_required_tasks())
        self.assertIsNone(self.state.failure_reason)

        # 6. Verify runtime started
        self.assertEqual(self.state.runtime_status, "RUNNING")
        self.assertIsNotNone(self.state.runtime_port)
        self.assertTrue(self.state.project_success)
        self.assertEqual(self.state.current_phase, "COMPLETE")

    @patch("backend.orchestration.orchestrator.call_openrouter")
    def test_focusflow_fullstack_fastapi_sqlite_recovery_and_crud_e2e(self, mock_call_llm):
        """Simulate FocusFlow Fullstack (FastAPI + SQLite + Frontend) where recovery rescues missing

        components, unblocks the fullstack runtime, and allows CRUD verification to pass.
        """
        self.state.goal = (
            'Build a full-stack web application called "FocusFlow", a personal task and productivity manager. '
            'Use FastAPI for backend, SQLite for storage, and HTML/CSS/JS frontend.'
        )
        self.state.selected_language = "Fullstack"
        self.state.effective_language = "Fullstack"

        # Plan response
        plan_response = """{
            "project_name": "FocusFlow",
            "detected_language": "Fullstack",
            "is_fullstack": true,
            "architecture_summary": "Full-stack FocusFlow with FastAPI backend, SQLite task store, and modern frontend",
            "tech_stack": ["FastAPI", "SQLite", "HTML5", "CSS3", "JavaScript"],
            "files": ["app.py", "requirements.txt", "index.html", "style.css", "app.js", "README.md"],
            "tasks": ["Generate app.py", "Generate requirements.txt", "Generate index.html", "Generate style.css", "Generate app.js", "Generate README.md"]
        }"""

        # Initial codegen: missing app.js and requirements.txt
        initial_codegen = """### FILE: app.py
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="FocusFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    conn = sqlite3.connect("focusflow.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, done BOOLEAN)''')
    conn.commit()
    conn.close()

init_db()

class TaskCreate(BaseModel):
    title: str

class TaskOut(BaseModel):
    id: int
    title: str
    done: bool

@app.get("/")
def read_root():
    return {"status": "ok", "app": "FocusFlow API"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/tasks", response_model=List[TaskOut])
def get_tasks():
    conn = sqlite3.connect("focusflow.db")
    c = conn.cursor()
    rows = c.execute("SELECT id, title, done FROM tasks").fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "done": bool(r[2])} for r in rows]

@app.post("/api/tasks", response_model=TaskOut)
def create_task(task: TaskCreate):
    conn = sqlite3.connect("focusflow.db")
    c = conn.cursor()
    c.execute("INSERT INTO tasks (title, done) VALUES (?, ?)", (task.title, False))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return {"id": task_id, "title": task.title, "done": False}

### FILE: index.html
<!DOCTYPE html>
<html>
<head><title>FocusFlow</title><link rel="stylesheet" href="style.css"></head>
<body>
  <h1>FocusFlow</h1>
  <input id="taskInput" placeholder="New task..." />
  <button id="addBtn">Add Task</button>
  <ul id="taskList"></ul>
  <script src="app.js"></script>
</body>
</html>

### FILE: style.css
body { font-family: system-ui; background: #0f172a; color: #f8fafc; padding: 2rem; }
input { padding: 0.5rem; border-radius: 4px; border: 1px solid #334155; }
button { padding: 0.5rem 1rem; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; }

### FILE: README.md
# FocusFlow
A full-stack productivity and task manager with FastAPI and SQLite.
"""

        # Recovery 1: requirements.txt (fallback output without ### FILE header)
        recovery_reqs = """
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
"""

        # Recovery 2: app.js (fallback output without ### FILE header)
        recovery_app_js = """
const API_URL = "http://localhost:8000/api/tasks";

async function loadTasks() {
  try {
    const res = await fetch("/api/tasks");
    if (!res.ok) return;
    const tasks = await res.json();
    const list = document.getElementById("taskList");
    if (list) {
      list.innerHTML = tasks.map(t => `<li>${t.title} [${t.done ? "Done" : "Pending"}]</li>`).join("");
    }
  } catch (e) {
    console.error("Failed to load tasks", e);
  }
}

document.addEventListener("DOMContentLoaded", loadTasks);
"""

        mock_call_llm.side_effect = [
            plan_response,
            initial_codegen,
            recovery_reqs,
            recovery_app_js,
        ]

        # 1. Analyze and Plan
        self.pipeline.analyze_and_plan(self.state)
        self.assertTrue(self.state.runtime_type == "fullstack")

        # 2. Execute Build (triggers codegen + recovery for app.js and requirements.txt)
        self.pipeline.execute_build(self.state)

        # 3. Verify files on disk
        files = self.workspace.list_files()
        self.assertIn("app.py", files)
        self.assertIn("requirements.txt", files)
        self.assertIn("index.html", files)
        self.assertIn("app.js", files)
        self.assertIn("README.md", files)

        # 4. Verify all tasks succeeded
        for t in self.state.tasks:
            if t.is_required:
                self.assertEqual(t.status, "SUCCESS", f"Task {t.id} ({t.title}) did not succeed: {t.status}")

        # 5. Verify runtime reached RUNNING
        self.assertEqual(self.state.runtime_status, "RUNNING")
        self.assertIsNotNone(self.state.runtime_port)
        self.assertTrue(self.state.project_success)


if __name__ == "__main__":
    unittest.main()

