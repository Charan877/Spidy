"""Unit tests for ArchitectureContract extraction and canonical file generation."""

import unittest
from backend.core.architecture_contract import (
    ArchitectureContract,
    extract_architecture_contract,
    generate_compliant_fullstack_files,
)


class TestArchitectureContract(unittest.TestCase):
    def test_extract_spendwise_contract(self):
        req = (
            'Build a full-stack web application called "SpendWise", a personal expense tracking and budgeting application. '
            'Required stack: React, TypeScript, Vite, FastAPI, SQLite, REST API, frontend/backend communication.'
        )
        contract = extract_architecture_contract(req)

        self.assertEqual(contract.project_name, "SpendWise")
        self.assertEqual(contract.project_type, "fullstack")
        self.assertTrue(contract.is_strict_fullstack)
        self.assertEqual(contract.frontend_framework, "React")
        self.assertEqual(contract.frontend_language, "TypeScript")
        self.assertEqual(contract.frontend_tooling, "Vite")
        self.assertEqual(contract.backend_framework, "FastAPI")
        self.assertEqual(contract.backend_language, "Python")
        self.assertEqual(contract.database_engine, "SQLite")
        self.assertEqual(contract.communication_protocol, "REST API")
        self.assertIn("frontend", contract.required_layers)
        self.assertIn("backend", contract.required_layers)
        self.assertIn("database", contract.required_layers)

        # Check prompt instructions forbid downgrading
        instructions = contract.to_prompt_instructions()
        self.assertIn("AUTHORITATIVE ARCHITECTURE CONTRACT", instructions)
        self.assertIn("DO NOT DOWNGRADE", instructions)
        self.assertIn("React", instructions)
        self.assertIn("FastAPI", instructions)

    def test_generate_compliant_files_for_spendwise(self):
        req = (
            'Build a full-stack web application called "SpendWise". '
            'Required stack: React, TypeScript, Vite, FastAPI, SQLite.'
        )
        contract = extract_architecture_contract(req)
        files = generate_compliant_fullstack_files(contract)

        # Must include React + Vite files
        self.assertIn("package.json", files)
        self.assertIn("vite.config.ts", files)
        self.assertIn("src/main.tsx", files)
        self.assertIn("src/App.tsx", files)

        # Must include FastAPI backend files
        self.assertIn("requirements.txt", files)
        self.assertIn("app/main.py", files)
        self.assertIn("app/database.py", files)

        # Must not contain placeholder paths
        for f in files:
            self.assertFalse("path/to" in f)
            self.assertFalse("your_file" in f)

    def test_extract_vanilla_web_contract(self):
        req = "Build a simple counter web application using HTML, CSS, and JavaScript."
        contract = extract_architecture_contract(req)
        self.assertFalse(contract.is_strict_fullstack)
        self.assertEqual(contract.project_type, "web")
        self.assertEqual(contract.frontend_framework, "Static HTML")

    def test_extract_cli_contract(self):
        req = "Build a Python CLI tool to calculate Fibonacci numbers."
        contract = extract_architecture_contract(req)
        self.assertFalse(contract.is_strict_fullstack)
        self.assertEqual(contract.project_type, "cli")
        self.assertEqual(contract.backend_language, "Python")


if __name__ == "__main__":
    unittest.main()
