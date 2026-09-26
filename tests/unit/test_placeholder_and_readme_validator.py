"""Unit tests for placeholder path detector and README content validator."""

import unittest
from backend.core.artifact_validator import is_placeholder_path, validate_readme_content
from backend.core.openrouter_client import parse_multi_file_response


class TestPlaceholderAndReadmeValidator(unittest.TestCase):
    def test_placeholder_path_detection(self):
        placeholders = [
            "path/to/file.ext",
            "/path/to/file.ext",
            "path/to/file",
            "example_file.ext",
            "your_file_here.ext",
            "filename.ext",
            "file.ext",
            "main_output",
            "output.txt",
        ]
        for p in placeholders:
            is_ph, reason = is_placeholder_path(p)
            self.assertTrue(is_ph, f"Expected '{p}' to be detected as placeholder")

    def test_valid_file_paths_not_flagged_as_placeholders(self):
        valid_paths = [
            "src/main.tsx",
            "src/App.tsx",
            "app/main.py",
            "app/database.py",
            "package.json",
            "tsconfig.json",
            "vite.config.ts",
            "index.html",
            "style.css",
            "script.js",
            "README.md",
            "requirements.txt",
        ]
        for v in valid_paths:
            is_ph, reason = is_placeholder_path(v)
            self.assertFalse(is_ph, f"Valid path '{v}' was incorrectly flagged: {reason}")

    def test_readme_rejects_generic_boilerplate(self):
        boilerplate = """# Project

This is a generic repository.

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature`)
3. Open a pull request

## License
MIT License
"""
        is_valid, reason = validate_readme_content(
            content=boilerplate,
            project_name="SpendWise",
            goal="Build a personal expense tracking and budgeting application",
        )
        self.assertFalse(is_valid)
        self.assertIn("boilerplate", reason.lower())

    def test_readme_accepts_project_specific_content(self):
        spendwise_readme = """# SpendWise - Personal Expense Tracker

SpendWise is a personal expense tracking and budgeting web application.

## Tech Stack
- Frontend: React 18, TypeScript, Vite
- Backend: FastAPI, Python 3
- Database: SQLite

## API Endpoints
- `GET /api/expenses` - Retrieve all expenses
- `POST /api/expenses` - Add a new expense
- `GET /health` - API health check

## Running the Application
Run the backend with uvicorn and start the frontend with vite.
"""
        is_valid, reason = validate_readme_content(
            content=spendwise_readme,
            project_name="SpendWise",
            goal="Build a personal expense tracking and budgeting application",
        )
        self.assertTrue(is_valid)

    def test_parser_strips_placeholder_files(self):
        response_with_placeholder = """### FILE: path/to/file.ext
```python
# Generic dummy
```

### FILE: app/main.py
```python
from fastapi import FastAPI
app = FastAPI()
```
"""
        parsed = parse_multi_file_response(response_with_placeholder)
        self.assertIn("app/main.py", parsed)
        self.assertNotIn("path/to/file.ext", parsed)
        self.assertNotIn("main_output", parsed)


if __name__ == "__main__":
    unittest.main()
