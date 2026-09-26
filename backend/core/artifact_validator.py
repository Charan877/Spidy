"""Artifact and Response Validator for SPIDY.

Performs deterministic structural and content validation on generated code
artifacts before they can transition a task to SUCCESS or RECOVERED.
Prevents materialization of placeholder paths and generic documentation.
"""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

REFUSAL_OR_ERROR_INDICATORS = [
    "i cannot fulfill this request",
    "i apologize, but",
    "as an ai,",
    "rate limit exceeded",
    "error: 429",
    "error: 500",
    "error: 502",
    "error: 503",
    "error: 504",
    '{"error":',
    "traceback (most recent call last):",
]

PLACEHOLDER_PATH_PATTERNS = [
    r"^path/to/file(?:\.ext)?$",
    r"^/path/to/file",
    r"^path/to/",
    r"^/path/",
    r"^example_file(?:\.ext)?$",
    r"^your_file_here(?:\.ext)?$",
    r"^your_file(?:\.ext)?$",
    r"^filename(?:\.ext)?$",
    r"^file\.ext$",
    r"^code\.ext$",
    r"^main_output$",
    r"^output\.txt$",
    r"^sample\.ext$",
]


def is_placeholder_path(file_path: str) -> Tuple[bool, str]:
    """Check if a file path is an obvious LLM placeholder or generic example.

    Returns:
        Tuple of (is_placeholder: bool, reason: str)
    """
    clean = (file_path or "").strip().replace("\\", "/").lstrip("/")
    if not clean:
        return True, "Path is empty."

    clean_lower = clean.lower()

    for pattern in PLACEHOLDER_PATH_PATTERNS:
        if re.search(pattern, clean_lower):
            return True, f"Matches placeholder pattern: '{pattern}'"

    # Component checks: any segment named 'path' followed by 'to'
    segments = clean_lower.split("/")
    if "path" in segments and "to" in segments:
        return True, "Path contains 'path/to' segment."
    if any(s.startswith("your_") or s.startswith("example_") for s in segments):
        return True, "Path contains placeholder prefix ('your_' or 'example_')."

    return False, "Valid artifact path."


def validate_readme_content(
    content: str,
    project_name: str = "Project",
    goal: str = "",
    tech_stack: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """Validate that generated README is relevant to the current project and not generic repo boilerplate.

    Returns:
        Tuple of (is_valid: bool, reason: str)
    """
    if not content or len(content.strip()) < 50:
        return False, "README is too short or empty (< 50 characters)."

    content_lower = content.lower()
    pname_lower = (project_name or "").lower()

    # Generic boilerplate signals
    generic_signals = [
        "fork the repository",
        "create your feature branch",
        "open a pull request",
        "git checkout -b feature",
    ]
    has_boilerplate = any(sig in content_lower for sig in generic_signals)

    # Check if project name or domain concepts appear
    has_pname = bool(pname_lower and pname_lower not in ("spidy project", "spidy application") and pname_lower in content_lower)

    # Extract domain words from goal
    goal_words = [
        w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", goal)
        if w.lower() not in ("build", "full", "stack", "application", "project", "using", "with", "make", "create", "need", "want")
    ]
    domain_matches = [w for w in goal_words if w in content_lower]

    if has_boilerplate and not has_pname and len(domain_matches) < 2:
        return (
            False,
            "README is generic repository boilerplate ('Fork the repository' / 'MIT License') with no project-specific features or context.",
        )

    # Check if README starts immediately with contributing/license with no project header
    first_lines = "\n".join(content.splitlines()[:5]).lower()
    if ("contributing" in first_lines or "license" in first_lines) and "#" in first_lines and not has_pname:
        return False, "README begins with Contributing/License rather than a project title and overview."

    return True, "README content is relevant to project."


def validate_artifact(
    file_path: str,
    content: str,
    workspace_dir: Optional[Path] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate a generated code artifact against structural, placeholder, and sanity requirements.

    Args:
        file_path: Target relative path of the file (e.g. 'script.js', 'app.py').
        content: The code content generated for the file.
        workspace_dir: Optional path to workspace on disk.

    Returns:
        Tuple of (is_valid: bool, reason: str, details: Dict[str, Any])
    """
    clean_path = file_path.strip().replace("\\", "/").lstrip("/")
    stripped_content = content.strip() if content else ""

    details: Dict[str, Any] = {
        "file_path": clean_path,
        "size_bytes": len(content.encode("utf-8")) if content else 0,
        "line_count": len(stripped_content.splitlines()),
        "checks": {},
    }

    # 1. Filename & Placeholder Path Check
    is_ph, ph_reason = is_placeholder_path(clean_path)
    if is_ph:
        details["checks"]["path_valid"] = False
        return False, f"Invalid or placeholder artifact filename '{clean_path}': {ph_reason}", details
    details["checks"]["path_valid"] = True

    # 2. Non-empty Content Check (minimum 10 characters)
    if len(stripped_content) < 10:
        details["checks"]["non_empty"] = False
        return False, f"Artifact '{clean_path}' is empty or trivial (< 10 chars)", details
    details["checks"]["non_empty"] = True

    # 3. Refusal / Upstream Error Check
    lower_content = stripped_content.lower()
    for indicator in REFUSAL_OR_ERROR_INDICATORS:
        if indicator in lower_content[:300]:
            details["checks"]["no_refusal_or_error"] = False
            return False, f"Artifact '{clean_path}' contains provider refusal or error string: '{indicator}'", details
    details["checks"]["no_refusal_or_error"] = True

    # 4. Syntax & Language-Specific Sanity
    ext = Path(clean_path).suffix.lower()

    if ext == ".py":
        try:
            compile(stripped_content, clean_path, "exec")
            details["checks"]["syntax_valid"] = True
        except SyntaxError as syn_err:
            details["checks"]["syntax_valid"] = False
            return False, f"Python syntax error in '{clean_path}': {syn_err}", details

    elif ext == ".json":
        try:
            json.loads(stripped_content)
            details["checks"]["json_valid"] = True
        except Exception as json_err:
            details["checks"]["json_valid"] = False
            return False, f"Malformed JSON in '{clean_path}': {json_err}", details

    elif ext == ".html":
        has_html_structure = (
            "<html" in lower_content
            or "<!doctype" in lower_content
            or "<body" in lower_content
            or "<div" in lower_content
            or "<head" in lower_content
        )
        if not has_html_structure:
            details["checks"]["html_structure"] = False
            return False, f"HTML file '{clean_path}' missing structural HTML tags", details
        details["checks"]["html_structure"] = True

    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        # Check that it's not pure markdown explanation without code
        if (
            stripped_content.startswith("#")
            and "```" not in stripped_content
            and "function" not in stripped_content
            and "const " not in stripped_content
            and "let " not in stripped_content
            and "import " not in stripped_content
        ):
            details["checks"]["script_structure"] = False
            return False, f"Script file '{clean_path}' contains prose/markdown instead of code", details
        details["checks"]["script_structure"] = True

    elif ext == ".md":
        details["checks"]["text_valid"] = True

    # 5. Optional Disk Check
    if workspace_dir:
        disk_file = Path(workspace_dir) / clean_path
        if disk_file.exists():
            disk_size = disk_file.stat().st_size
            details["checks"]["disk_exists"] = True
            details["checks"]["disk_size"] = disk_size
        else:
            details["checks"]["disk_exists"] = False

    return True, f"Artifact '{clean_path}' passed validation", details
