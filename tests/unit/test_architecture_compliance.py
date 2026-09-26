"""Unit tests for Architecture Compliance Validator (plan compliance & artifact compliance)."""

import unittest
from backend.core.architecture_contract import extract_architecture_contract
from backend.core.architecture_validator import (
    validate_plan_compliance,
    validate_architecture_compliance,
)


class TestArchitectureCompliance(unittest.TestCase):
    def setUp(self):
        self.req = (
            'Build a full-stack web application called "SpendWise". '
            'Required stack: React, TypeScript, Vite, FastAPI, SQLite.'
        )
        self.contract = extract_architecture_contract(self.req)

    def test_plan_compliance_rejects_vanilla_downgrade(self):
        """Plan proposing only index.html, style.css, script.js for React fullstack is rejected."""
        downgraded_plan = {
            "project_name": "SpendWise",
            "architecture_summary": "Vanilla web app",
            "files": ["index.html", "style.css", "script.js", "README.md"],
            "tasks": ["index.html", "style.css", "script.js"],
        }
        is_compliant, reason = validate_plan_compliance(self.contract, downgraded_plan)
        self.assertFalse(is_compliant)
        self.assertIn("missing backend components", reason.lower())

    def test_plan_compliance_rejects_react_downgrade_with_backend(self):
        """Plan with FastAPI backend but vanilla static frontend is rejected when React is requested."""
        downgraded_plan = {
            "project_name": "SpendWise",
            "architecture_summary": "FastAPI + vanilla HTML",
            "files": ["app.py", "requirements.txt", "index.html", "style.css", "script.js"],
            "tasks": ["app.py", "index.html"],
        }
        is_compliant, reason = validate_plan_compliance(self.contract, downgraded_plan)
        self.assertFalse(is_compliant)
        self.assertIn("downgraded requested react", reason.lower())

    def test_plan_compliance_rejects_placeholder_files(self):
        """Plan containing placeholder paths like 'path/to/file.ext' is rejected."""
        placeholder_plan = {
            "project_name": "SpendWise",
            "architecture_summary": "SpendWise fullstack",
            "files": ["app/main.py", "path/to/file.ext", "package.json", "src/App.tsx"],
            "tasks": ["app/main.py"],
        }
        is_compliant, reason = validate_plan_compliance(self.contract, placeholder_plan)
        self.assertFalse(is_compliant)
        self.assertIn("placeholder file path", reason.lower())

    def test_plan_compliance_accepts_valid_react_fastapi_plan(self):
        """Valid plan with React components and FastAPI entrypoints passes."""
        valid_plan = {
            "project_name": "SpendWise",
            "architecture_summary": "React + Vite frontend with FastAPI backend and SQLite",
            "files": [
                "requirements.txt",
                "app/main.py",
                "app/database.py",
                "package.json",
                "vite.config.ts",
                "src/main.tsx",
                "src/App.tsx",
                "README.md",
            ],
            "tasks": ["app/main.py", "src/App.tsx"],
        }
        is_compliant, reason = validate_plan_compliance(self.contract, valid_plan)
        self.assertTrue(is_compliant)
        self.assertIsNone(reason)

    def test_architecture_compliance_detects_missing_react(self):
        """Artifact compliance fails if React components or package.json are missing."""
        files = {
            "app/main.py": "from fastapi import FastAPI\napp = FastAPI()",
            "index.html": "<!DOCTYPE html><html><body>SpendWise</body></html>",
            "style.css": "body { margin: 0; }",
        }
        is_compliant, missing, reason = validate_architecture_compliance(self.contract, files)
        self.assertFalse(is_compliant)
        self.assertIn("frontend (React)", missing)

    def test_architecture_compliance_detects_missing_fastapi(self):
        """Artifact compliance fails if FastAPI backend is missing."""
        files = {
            "package.json": '{"name": "spendwise-fe", "dependencies": {"react": "^18.0.0"}}',
            "src/App.tsx": "export default function App() { return <div>SpendWise</div>; }",
            "src/main.tsx": "import React from 'react';",
            "index.html": "<!DOCTYPE html><html><body><div id='root'></div></body></html>",
        }
        is_compliant, missing, reason = validate_architecture_compliance(self.contract, files)
        self.assertFalse(is_compliant)
        self.assertIn("backend (FastAPI)", missing)

    def test_architecture_compliance_passes_when_all_layers_present(self):
        """Artifact compliance passes when React, FastAPI, and SQLite layers are implemented."""
        files = {
            "package.json": '{"name": "spendwise-fe", "dependencies": {"react": "^18.0.0"}}',
            "src/App.tsx": "export default function App() { fetch('/api/expenses'); return <div>SpendWise</div>; }",
            "src/main.tsx": "import React from 'react';",
            "app/main.py": (
                "from fastapi import FastAPI\n"
                "import sqlite3\n"
                "app = FastAPI(title='SpendWise API')\n"
                "@app.get('/health')\ndef health(): return {'status': 'healthy'}\n"
            ),
            "app/database.py": "import sqlite3\ndef get_db(): return sqlite3.connect('spendwise.db')",
        }
        is_compliant, missing, reason = validate_architecture_compliance(self.contract, files)
        self.assertTrue(is_compliant)
        self.assertEqual(len(missing), 0)


if __name__ == "__main__":
    unittest.main()
