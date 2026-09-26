"""Authoritative Architecture Contract Engine for SPIDY.

Extracts, enforces, and validates explicit technology stack contracts
from user requirements. Guarantees that requested fullstack stacks
(e.g. React + TypeScript + Vite, FastAPI, SQLite) are never silently
downgraded into generic HTML/CSS/JS templates.
"""

from dataclasses import asdict, dataclass, field
import json
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ArchitectureContract:
    """Explicit architecture contract defining the expected technology layers."""

    project_name: str
    project_type: str  # "fullstack", "web", "api", "cli", "library"
    effective_language: str

    # Frontend specifications
    frontend_framework: str  # "React", "Vue", "Svelte", "Next.js", "Static HTML", "None"
    frontend_language: str   # "TypeScript", "JavaScript", "HTML/CSS", "None"
    frontend_tooling: str    # "Vite", "Create React App", "Next.js", "None"
    frontend_entrypoint: Optional[str] = None  # e.g. "src/main.tsx", "index.html"
    frontend_required_artifacts: List[str] = field(default_factory=list)

    # Backend specifications
    backend_framework: str = "None"  # "FastAPI", "Flask", "Express", "None"
    backend_language: str = "None"   # "Python", "Node.js", "None"
    backend_entrypoint: Optional[str] = None  # e.g. "app/main.py", "app.py"
    backend_required_artifacts: List[str] = field(default_factory=list)
    api_routes: List[str] = field(default_factory=list)

    # Database specifications
    database_engine: str = "None"  # "SQLite", "PostgreSQL", "MongoDB", "None"
    database_file: Optional[str] = None  # e.g. "spendwise.db"
    database_required_artifacts: List[str] = field(default_factory=list)

    # Integration specifications
    communication_protocol: str = "None"  # "REST API", "WebSocket", "GraphQL", "None"
    crud_resource_name: str = "item"     # e.g. "expense", "task"
    test_crud_endpoint: str = "/api/items"
    test_crud_payload: Dict[str, Any] = field(default_factory=dict)

    # Required architectural layers to validate
    required_layers: List[str] = field(default_factory=list)
    is_strict_fullstack: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert contract to dictionary representation."""
        return asdict(self)

    def to_prompt_instructions(self) -> str:
        """Generate mandatory instructions for Planner and Developer LLM agents."""
        lines = [
            "============================================================",
            "AUTHORITATIVE ARCHITECTURE CONTRACT (STRICT ENFORCEMENT)",
            "============================================================",
            f"Project Name: {self.project_name}",
            f"Project Architecture Type: {self.project_type.upper()}",
            f"Required Stack:",
        ]

        if self.frontend_framework != "None":
            tooling_str = f" with {self.frontend_tooling}" if self.frontend_tooling != "None" else ""
            lines.append(f"- Frontend: {self.frontend_framework} ({self.frontend_language}){tooling_str}")
        if self.backend_framework != "None":
            lines.append(f"- Backend: {self.backend_framework} ({self.backend_language})")
        if self.database_engine != "None":
            lines.append(f"- Database: {self.database_engine}")
        if self.communication_protocol != "None":
            lines.append(f"- Communication: {self.communication_protocol}")

        lines.extend([
            "",
            "CRITICAL ARCHITECTURAL CONSTRAINTS:",
        ])

        if self.is_strict_fullstack:
            lines.append(
                "- DO NOT DOWNGRADE TO STATIC HTML/CSS/JS. The user explicitly requested a full-stack application."
            )
            if "React" in self.frontend_framework:
                lines.append(
                    "- You MUST produce a genuine React application (package.json, Vite configuration, TypeScript source in src/)."
                )
            if "FastAPI" in self.backend_framework:
                lines.append(
                    "- You MUST produce a genuine FastAPI backend (Python application, requirements.txt, REST API endpoints)."
                )
            if "SQLite" in self.database_engine:
                lines.append(
                    "- You MUST provide SQLite database initialization, models, and persistence."
                )
            lines.append(
                "- You MUST provide real frontend/backend REST integration with fetch() calls to the backend API."
            )

        lines.extend([
            "- DO NOT use placeholder filenames like 'path/to/file.ext' or '/path/to/file'.",
            "============================================================",
        ])
        return "\n".join(lines)


def _detect_resource_name(goal: str) -> Tuple[str, str, Dict[str, Any]]:
    """Derive representative CRUD resource name, endpoint, and test payload from requirement."""
    goal_lower = goal.lower()
    if "spend" in goal_lower or "expense" in goal_lower or "budget" in goal_lower:
        return "expense", "/api/expenses", {"title": "Office Supplies", "amount": 42.50, "category": "Work"}
    elif "task" in goal_lower or "todo" in goal_lower or "focus" in goal_lower:
        return "task", "/api/tasks", {"title": "Complete Quarterly Report", "done": False}
    elif "contact" in goal_lower or "crm" in goal_lower:
        return "contact", "/api/contacts", {"name": "Alice Johnson", "email": "alice@example.com"}
    elif "product" in goal_lower or "inventory" in goal_lower:
        return "product", "/api/products", {"name": "Mechanical Keyboard", "price": 99.00}
    elif "habit" in goal_lower:
        return "habit", "/api/habits", {"title": "Morning Run", "frequency": "daily"}
    return "item", "/api/items", {"title": "Sample Record", "description": "Automated test item"}


def extract_architecture_contract(
    requirement: str,
    plan_data: Optional[Dict[str, Any]] = None,
    selected_language: str = "Auto Detect",
) -> ArchitectureContract:
    """Analyze the user requirement and generate the authoritative architecture contract."""
    req_lower = (requirement or "").lower()
    plan_data = plan_data or {}

    # Extract or infer project name
    project_name = plan_data.get("project_name")
    if not project_name or project_name in ("SPIDY Project", "SPIDY Application"):
        name_match = re.search(r'called\s+["\']?([^"\'\s,.]+)["\']?', requirement, re.IGNORECASE)
        if name_match:
            project_name = name_match.group(1).strip()
        elif "spendwise" in req_lower:
            project_name = "SpendWise"
        elif "focusflow" in req_lower:
            project_name = "FocusFlow"
        elif "taskflow" in req_lower:
            project_name = "TaskFlow"
        else:
            project_name = "SPIDY Application"

    # Analyze frontend requirements
    has_react = "react" in req_lower
    has_vue = "vue" in req_lower
    has_svelte = "svelte" in req_lower
    has_next = "next.js" in req_lower or "nextjs" in req_lower
    has_ts = "typescript" in req_lower or "ts" in req_lower
    has_vite = "vite" in req_lower

    web_signals = ["web", "html", "react", "vue", "svelte", "frontend", "dashboard"]
    has_web_intent = any(w in req_lower for w in web_signals) or bool(re.search(r"\bui\b", req_lower))

    if has_next:
        fe_framework = "Next.js"
        fe_lang = "TypeScript" if has_ts else "JavaScript"
        fe_tooling = "Next.js"
        fe_entry = "pages/index.tsx" if has_ts else "pages/index.js"
    elif has_react:
        fe_framework = "React"
        fe_lang = "TypeScript" if (has_ts or has_vite or "typescript" in req_lower) else "JavaScript"
        fe_tooling = "Vite" if has_vite else "Create React App"
        fe_entry = "src/main.tsx" if fe_lang == "TypeScript" else "src/main.jsx"
    elif has_vue:
        fe_framework = "Vue"
        fe_lang = "TypeScript" if has_ts else "JavaScript"
        fe_tooling = "Vite" if has_vite else "Vue CLI"
        fe_entry = "src/main.ts" if fe_lang == "TypeScript" else "src/main.js"
    elif has_svelte:
        fe_framework = "Svelte"
        fe_lang = "TypeScript" if has_ts else "JavaScript"
        fe_tooling = "Vite"
        fe_entry = "src/main.ts" if fe_lang == "TypeScript" else "src/main.js"
    elif ("cli" in req_lower or "command line" in req_lower or "terminal" in req_lower) and not has_web_intent:
        fe_framework = "None"
        fe_lang = "None"
        fe_tooling = "None"
        fe_entry = None
    else:
        fe_framework = "Static HTML"
        fe_lang = "HTML/CSS"
        fe_tooling = "None"
        fe_entry = "index.html"

    # Analyze backend requirements
    has_fastapi = "fastapi" in req_lower
    has_flask = "flask" in req_lower
    has_express = "express" in req_lower or "node" in req_lower and "backend" in req_lower
    has_python_backend = has_fastapi or has_flask or ("python" in req_lower and any(w in req_lower for w in ["backend", "api", "rest"]))

    if has_fastapi or (has_python_backend and not has_flask):
        be_framework = "FastAPI"
        be_lang = "Python"
        be_entry = "app/main.py"
    elif has_flask:
        be_framework = "Flask"
        be_lang = "Python"
        be_entry = "app.py"
    elif has_express:
        be_framework = "Express"
        be_lang = "Node.js"
        be_entry = "server.js"
    elif "cli" in req_lower or "command line" in req_lower:
        be_framework = "CLI"
        be_lang = "Python" if "python" in req_lower else "Python"
        be_entry = "main.py"
    else:
        be_framework = "None"
        be_lang = "None"
        be_entry = None

    # Analyze database requirements
    has_sqlite = "sqlite" in req_lower or "sqlite3" in req_lower
    has_postgres = "postgres" in req_lower or "postgresql" in req_lower
    has_mongodb = "mongo" in req_lower or "mongodb" in req_lower

    if has_sqlite:
        db_engine = "SQLite"
        db_file = f"{project_name.lower().replace(' ', '_')}.db"
    elif has_postgres:
        db_engine = "PostgreSQL"
        db_file = None
    elif has_mongodb:
        db_engine = "MongoDB"
        db_file = None
    elif be_framework != "None" and any(k in req_lower for k in ["database", "crud", "storage", "persistence", "budget", "expense", "task"]):
        db_engine = "SQLite"
        db_file = f"{project_name.lower().replace(' ', '_')}.db"
    else:
        db_engine = "None"
        db_file = None

    # Determine Project Type and Full-Stack status
    is_fullstack = (
        (be_framework != "None" and fe_framework != "None")
        or "full-stack" in req_lower
        or "fullstack" in req_lower
        or selected_language == "Fullstack"
        or plan_data.get("is_fullstack", False)
    )

    if is_fullstack:
        project_type = "fullstack"
        effective_lang = "Fullstack"
        if be_framework == "None":
            be_framework = "FastAPI"
            be_lang = "Python"
            be_entry = "app/main.py"
        if db_engine == "None":
            db_engine = "SQLite"
            db_file = f"{project_name.lower().replace(' ', '_')}.db"
        comm_protocol = "REST API"
    elif "cli" in req_lower or "command line" in req_lower:
        project_type = "cli"
        effective_lang = "Python" if "python" in req_lower else selected_language
        comm_protocol = "None"
    elif be_framework != "None":
        project_type = "api"
        effective_lang = be_lang
        comm_protocol = "REST API"
    elif fe_framework != "None":
        project_type = "web"
        effective_lang = fe_framework if fe_framework != "Static HTML" else "HTML/CSS/JS"
        comm_protocol = "None"
    else:
        project_type = "web"
        effective_lang = selected_language if selected_language != "Auto Detect" else "Python"
        comm_protocol = "None"

    # Derive CRUD details
    res_name, crud_endpoint, crud_payload = _detect_resource_name(requirement)

    # Build required layers list
    required_layers = []
    if fe_framework != "None":
        required_layers.append("frontend")
    if be_framework != "None":
        required_layers.append("backend")
    if db_engine != "None":
        required_layers.append("database")
    if comm_protocol != "None" and be_framework != "None":
        required_layers.append("api")
    if is_fullstack:
        required_layers.append("integration")

    # Required artifacts per layer
    fe_artifacts = []
    if fe_framework in ("React", "Vue", "Svelte"):
        fe_artifacts.extend(["package.json", "index.html", fe_entry or "src/main.tsx"])
        if fe_tooling == "Vite":
            fe_artifacts.append("vite.config.ts" if fe_lang == "TypeScript" else "vite.config.js")
    elif fe_framework == "Static HTML":
        fe_artifacts.extend(["index.html", "style.css", "script.js"])

    be_artifacts = []
    if be_framework in ("FastAPI", "Flask"):
        be_artifacts.extend(["requirements.txt", be_entry or "app/main.py"])
    elif be_framework == "Express":
        be_artifacts.extend(["package.json", be_entry or "server.js"])

    db_artifacts = []
    if db_engine == "SQLite":
        if be_framework == "FastAPI":
            db_artifacts.append("app/database.py")
        elif be_framework == "Flask":
            db_artifacts.append("database.py")

    return ArchitectureContract(
        project_name=project_name,
        project_type=project_type,
        effective_language=effective_lang,
        frontend_framework=fe_framework,
        frontend_language=fe_lang,
        frontend_tooling=fe_tooling,
        frontend_entrypoint=fe_entry,
        frontend_required_artifacts=fe_artifacts,
        backend_framework=be_framework,
        backend_language=be_lang,
        backend_entrypoint=be_entry,
        backend_required_artifacts=be_artifacts,
        api_routes=[crud_endpoint, f"{crud_endpoint}/{{id}}", "/health"],
        database_engine=db_engine,
        database_file=db_file,
        database_required_artifacts=db_artifacts,
        communication_protocol=comm_protocol,
        crud_resource_name=res_name,
        test_crud_endpoint=crud_endpoint,
        test_crud_payload=crud_payload,
        required_layers=required_layers,
        is_strict_fullstack=is_fullstack,
    )


def generate_compliant_fullstack_files(contract: ArchitectureContract) -> List[str]:
    """Generate canonical required file paths for a compliant fullstack architecture."""
    if not contract.is_strict_fullstack:
        if contract.project_type == "web":
            return ["index.html", "style.css", "script.js", "README.md"]
        elif contract.project_type == "api":
            return ["app.py", "requirements.txt", "README.md"]
        return ["main.py", "README.md"]

    res_plural = contract.test_crud_endpoint.split("/")[-1] or "items"

    if contract.frontend_framework == "React":
        files = [
            # Backend
            "requirements.txt",
            "app/config.py",
            "app/database.py",
            "app/models.py",
            "app/schemas.py",
            f"app/routers/{res_plural}.py",
            "app/main.py",
            # Frontend
            "package.json",
            "tsconfig.json",
            "vite.config.ts",
            "index.html",
            "src/main.tsx",
            "src/App.tsx",
            "src/App.css",
            "src/types/index.ts",
            "src/services/api.ts",
            f"src/components/{contract.crud_resource_name.capitalize()}List.tsx",
            f"src/components/{contract.crud_resource_name.capitalize()}Form.tsx",
            # Documentation
            "README.md",
        ]
    else:
        # Standard web fullstack
        files = [
            "requirements.txt",
            "app/database.py",
            "app/main.py",
            "index.html",
            "style.css",
            "app.js",
            "README.md",
        ]

    return files
