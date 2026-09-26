"""Architecture Compliance Validator for SPIDY.

Validates that plans and generated artifacts deterministically comply with
the authoritative ArchitectureContract, preventing silent downgrades,
placeholder file materialization, and architectural omissions.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.core.architecture_contract import ArchitectureContract
from backend.core.artifact_validator import is_placeholder_path


def validate_plan_compliance(
    contract: ArchitectureContract,
    plan_data: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """Validate that a planned task spec / file list aligns with the ArchitectureContract."""
    if not contract.is_strict_fullstack:
        return True, None

    files = [str(f).strip().replace("\\", "/").lower() for f in plan_data.get("files", [])]
    summary = str(plan_data.get("architecture_summary", "")).lower()

    # Check 1: Fullstack must have both frontend and backend planned
    has_be_file = any(f.endswith(".py") or f.endswith("requirements.txt") for f in files)
    has_fe_file = any(f.endswith((".html", ".css", ".js", ".ts", ".jsx", ".tsx", "package.json")) for f in files)

    if not has_be_file and not has_fe_file:
        return False, "Plan contains neither backend nor frontend files for fullstack requirement."
    if not has_be_file:
        return False, f"Plan is missing backend components for {contract.backend_framework} ({contract.backend_language})."
    if not has_fe_file:
        return False, f"Plan is missing frontend components for {contract.frontend_framework}."

    # Check 2: If React was requested, reject vanilla HTML/CSS/JS plans
    if contract.frontend_framework == "React":
        has_react_artifact = any(
            f.endswith((".tsx", ".jsx", "package.json", "tsconfig.json", "vite.config.ts"))
            for f in files
        )
        if not has_react_artifact:
            return (
                False,
                "Plan downgraded requested React + TypeScript + Vite architecture to vanilla static HTML/CSS/JS.",
            )

    # Check 3: If FastAPI was requested, reject plans lacking Python API entrypoints
    if contract.backend_framework == "FastAPI":
        has_fastapi_file = any("main.py" in f or "app.py" in f or "routers" in f for f in files)
        if not has_fastapi_file:
            return False, "Plan is missing FastAPI entrypoint or router files."

    # Check 4: Reject placeholder files in plan
    for f in files:
        is_ph, ph_reason = is_placeholder_path(f)
        if is_ph:
            return False, f"Plan contains placeholder file path: '{f}' ({ph_reason})"

    return True, None


def validate_architecture_compliance(
    contract: ArchitectureContract,
    files: Dict[str, str],
    workspace_files: Optional[List[str]] = None,
    list_files_fn: Optional[Any] = None,
) -> Tuple[bool, List[str], str]:
    """Validate that generated artifacts on disk and in memory satisfy all architectural layers.

    Returns:
        Tuple of (is_compliant: bool, missing_layers: List[str], detailed_reason: str)
    """
    if not getattr(contract, "is_strict_fullstack", False):
        return True, [], "Architecture compliance check skipped for non-fullstack contract."

    if list_files_fn and not workspace_files:
        try:
            workspace_files = list_files_fn()
        except Exception:
            workspace_files = []

    all_files: Set[str] = set()
    for k in files.keys():
        all_files.add(k.strip().replace("\\", "/"))
    if workspace_files:
        for wf in workspace_files:
            all_files.add(wf.strip().replace("\\", "/"))

    combined_code = " ".join(files.values())
    missing_layers: List[str] = []
    issues: List[str] = []

    # Check 0: Reject placeholder files
    placeholder_files = [f for f in all_files if is_placeholder_path(f)[0]]
    if placeholder_files:
        issues.append(f"Workspace contains placeholder files: {', '.join(placeholder_files)}")

    # Check 1: Frontend Layer
    if "frontend" in contract.required_layers:
        has_fe = False
        if contract.frontend_framework == "React":
            has_react_components = any(
                f.endswith((".tsx", ".jsx")) for f in all_files
            )
            has_pkg = any("package.json" in f for f in all_files)
            if has_react_components or (has_pkg and "react" in combined_code.lower()):
                has_fe = True
            else:
                missing_layers.append("frontend (React)")
                issues.append(
                    "Requested React + TypeScript frontend, but no React components (.tsx/.jsx) or package.json found."
                )
        else:
            has_html = any(f.endswith(".html") for f in all_files)
            if has_html:
                has_fe = True
            else:
                missing_layers.append("frontend")
                issues.append("Frontend web interface (index.html) missing.")

    # Check 2: Backend Layer
    if "backend" in contract.required_layers:
        has_be = False
        if contract.backend_framework in ("FastAPI", "Flask"):
            has_py = any(f.endswith(".py") for f in all_files)
            has_framework = (
                contract.backend_framework.lower() in combined_code.lower()
                or "app = fastapi" in combined_code.lower()
                or "app = flask" in combined_code.lower()
            )
            if has_py and has_framework:
                has_be = True
            elif not has_py:
                missing_layers.append(f"backend ({contract.backend_framework})")
                issues.append(f"Requested {contract.backend_framework} backend, but no Python backend files exist.")
            else:
                missing_layers.append(f"backend ({contract.backend_framework})")
                issues.append(f"Python files exist, but missing {contract.backend_framework} initialization.")
        elif contract.backend_framework == "Express":
            has_js_server = any(f in ("server.js", "app.js", "src/server.ts") for f in all_files)
            if has_js_server and "express" in combined_code.lower():
                has_be = True
            else:
                missing_layers.append("backend (Express)")
                issues.append("Requested Express backend, but no Express server file found.")

    # Check 3: Database Layer
    if "database" in contract.required_layers:
        has_db = False
        if contract.database_engine == "SQLite":
            has_sqlite = (
                "sqlite3" in combined_code
                or "sqlite:" in combined_code
                or "sqlalchemy" in combined_code
                or any("database.py" in f or "models.py" in f for f in all_files)
            )
            if has_sqlite:
                has_db = True
            else:
                missing_layers.append("database (SQLite)")
                issues.append("Requested SQLite database layer, but no SQLite connection or models found.")

    # Check 4: REST API & Integration Layer
    if "api" in contract.required_layers and contract.communication_protocol == "REST API":
        has_api_routes = (
            "@app." in combined_code
            or "@router." in combined_code
            or "apirouter" in combined_code.lower()
            or "def read_root" in combined_code
            or "/api/" in combined_code
        )
        if not has_api_routes:
            missing_layers.append("api (REST routes)")
            issues.append("Backend missing REST API endpoint route definitions.")

    if "integration" in contract.required_layers:
        has_client_call = (
            "fetch(" in combined_code
            or "axios." in combined_code
            or "xmlhttprequest" in combined_code.lower()
        )
        if not has_client_call:
            missing_layers.append("integration (frontend API client)")
            issues.append("Frontend missing REST API integration calls (fetch/axios to backend endpoints).")

    is_compliant = (len(missing_layers) == 0 and len(placeholder_files) == 0)
    reason = "; ".join(issues) if issues else "Architecture contract satisfied."
    return is_compliant, missing_layers, reason
