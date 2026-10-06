"""Orchestrator and Multi-Agent Workflow Engine for NOVA Code Lab.

Orchestrates multi-agent pipelines with strict dependency gates:
DISCOVER -> PLAN -> ARCHITECT -> GENERATE -> BUILD -> RUN -> TEST -> DEBUG -> REVIEW -> DOCUMENT -> COMPLETE.
Prevents premature execution of downstream agents when workspace preconditions are not met.
"""

import json
from pathlib import Path
import re
import time
from typing import Dict, List, Optional, Tuple
import uuid
from backend.core.base_agent import BaseAgent
from backend.agents.reviewer_agent import ReviewerAgent, ReviewVerdict
from backend.core.estimation import BuildEstimator
from backend.core.history_manager import HistoryManager
from backend.core.openrouter_client import call_openrouter, parse_json_response, parse_multi_file_response, clean_code_block
from backend.runtime.project_runner import ProjectRunner
from backend.core.project_state import ProjectState
from backend.core.task_classifier import TaskClassifier, TaskClassification
from backend.core.agent_result import AgentResult
from backend.core.semantic_requirement import SemanticRequirementAnalyzer, EngineeringSpecification
from backend.core.architecture_contract import (
    ArchitectureContract,
    extract_architecture_contract,
    generate_compliant_fullstack_files,
)
from backend.core.architecture_validator import (
    validate_plan_compliance,
    validate_architecture_compliance,
)
from backend.core.artifact_validator import is_placeholder_path, validate_artifact, validate_readme_content
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.environment_detector import EnvironmentDetector
from backend.runtime.preview_manager import PreviewManager
from backend.verification.gate_evaluator import GateEvaluator


def validate_plan_against_requirement(requirement: str, plan_data: dict) -> Tuple[bool, Optional[str]]:
    """Validate that the generated plan aligns with requirement and contains no cross-project contamination."""
    req_lower = (requirement or "").lower()
    summary = (plan_data.get("architecture_summary") or "").lower()
    proj_name = (plan_data.get("project_name") or "").lower()
    files = [str(f).lower() for f in plan_data.get("files", [])]
    tasks_text = " ".join(
        [
            f"{t.get('title', '')} {t.get('file_path', '')}".lower()
            if isinstance(t, dict)
            else str(t).lower()
            for t in plan_data.get("tasks", [])
        ]
    )
    combined_plan = f"{summary} {proj_name} {' '.join(files)} {tasks_text}"

    # Signatures of unrelated projects / LeetCode puzzles
    contamination_signatures = [
        "merge_sorted_lists",
        "merge two sorted lists",
        "two-pointer",
        "two pointer",
        "leetcode",
        "add_numbers",
        "binary_search",
    ]

    for sig in contamination_signatures:
        if sig in combined_plan and sig not in req_lower:
            return False, f"Plan contains signature '{sig}' from unrelated project context."

    # If requirement demands fullstack / web app, reject CLI algorithm plans
    is_web_or_fullstack = any(
        k in req_lower for k in ["full-stack", "fullstack", "web", "dashboard", "fastapi", "react", "html", "taskflow"]
    )
    if is_web_or_fullstack:
        if "cli demo" in combined_plan or "two-pointer" in combined_plan or "algorithm explanation" in combined_plan:
            return False, "Plan proposes CLI algorithm instead of requested fullstack/web application."

    return True, None


class MultiAgentPipeline:
    """Coordinates agent execution across project phases with strict prerequisite gates."""

    def __init__(self, workspace: WorkspaceManager, runner: Optional[ProjectRunner] = None):
        self.workspace = workspace
        self.runner = runner or ProjectRunner(workspace)
        self.detector = getattr(self.runner, "detector", None) or EnvironmentDetector()
        self.orchestrator_agent = BaseAgent("Orchestrator", "Pipeline Controller")
        self.planner_agent = BaseAgent("Planner & Architect Agent", "Requirements & Design")
        self.developer_agent = BaseAgent("Developer Agent", "Code Generator")
        self.tester_agent = BaseAgent("Tester & Runner Agent", "Runtime Health & Verification")
        self.debugger_agent = BaseAgent("Debugger Agent", "Syntax & Runtime Debugger")
        self.documentation_agent = BaseAgent("Documentation Agent", "Docstrings & Specs")
        self.reviewer_agent = ReviewerAgent()

    def can_execute_plan(self, state: ProjectState) -> bool:
        """Verify that requirements exist and confirmation has been granted before planning."""
        if not (state.goal or state.requirements):
            return False
        if state.is_awaiting_confirmation() or not state.can_execute_engineering():
            return False
        return True

    def can_execute_build(self, state: ProjectState) -> bool:
        """Verify that architecture and requirements are prepared and confirmed before building."""
        if state.is_awaiting_confirmation():
            return False
        return bool(state.goal or state.requirements)

    def can_execute_run(self, state: ProjectState) -> bool:
        """Verify that project has been generated and workspace contains files before running."""
        if state.is_awaiting_confirmation():
            return False
        workspace_files = self.workspace.list_files()
        if not workspace_files or len(workspace_files) == 0:
            return False
        if state.has_failed_required_tasks(phase="BUILD"):
            return False
        if not state.is_project_generated:
            state.is_project_generated = True
            state.project_generation_status = "GENERATED"
        return True

    def can_execute_test(self, state: ProjectState) -> bool:
        """Verify that project is generated and runnable before testing."""
        if state.is_awaiting_confirmation():
            return False
        if not state.is_project_generated:
            return False
        workspace_files = self.workspace.list_files()
        if not workspace_files or len(workspace_files) == 0:
            return False
        return True

    def can_execute_debug(self, state: ProjectState) -> bool:
        """Verify that debugging is warranted: workspace exists, project generated, and not precondition failure."""
        if state.is_awaiting_confirmation():
            return False
        if not state.is_project_generated:
            return False
        workspace_files = self.workspace.list_files()
        if not workspace_files or len(workspace_files) == 0:
            return False
        if state.failure_classification == "PRECONDITION_FAILURE":
            return False
        return True

    def get_earliest_missing_prerequisite(self, state: ProjectState) -> str:
        """Trace pipeline backwards to identify the earliest unfulfilled prerequisite step."""
        if not state.goal:
            return "INTAKE"
        if not state.project_spec or not state.architecture_summary:
            return "PLANNING"
        workspace_files = self.workspace.list_files()
        if not state.is_project_generated or not workspace_files or len(workspace_files) == 0:
            return "BUILD"
        build_tasks = [t for t in state.tasks if t.phase == "BUILD"]
        if build_tasks and not any(t.status in ("SUCCESS", "completed") for t in build_tasks):
            return "BUILD"
        if state.runtime_status not in ("RUNNING", "VERIFYING", "STOPPED"):
            return "RUN"
        if not state.is_app_verified and state.is_web_project:
            return "TEST"
        return "COMPLETE"

    def understand_requirement(self, state: ProjectState) -> bool:
        """Phase 1A: Non-executing semantic requirement understanding layer.
        
        Builds EngineeringSpecification, determines domain, core capabilities, and concise
        interpretation. Halts execution if user confirmation is required.
        """
        state.transition_to("UNDERSTANDING", "Requirement received: analyzing intent and engineering scope...")
        state.original_goal = state.goal
        state.requirements = state.goal
        state.current_phase = "UNDERSTAND"
        state.add_activity("Requirement received: analyzing scope and technology stack...", level="run")

        contract = extract_architecture_contract(state.goal, selected_language=state.selected_language)
        state.architecture_contract = contract.to_dict()
        state.fullstack_contract = contract.to_dict()
        state.test_crud_endpoint = contract.test_crud_endpoint
        state.test_crud_payload = contract.test_crud_payload

        # Semantic Requirement Understanding Layer (non-executing)
        eng_spec = SemanticRequirementAnalyzer.analyze(
            requirement=state.goal,
            active_context=state.active_context,
            existing_project_spec=state.project_spec,
            selected_language=state.selected_language,
        )
        state.engineering_spec = eng_spec.to_dict()
        state.requirement_interpretation = eng_spec.concise_interpretation
        state.pending_intent = eng_spec.intent_classification
        state.pending_target_project_id = eng_spec.target_project_id
        state.pending_requirement = state.goal
        state.pending_confirmation_id = f"conf_{state.build_id}"

        # Determine whether auto-confirmation has been explicitly requested
        if not getattr(state, "auto_confirm", False):
            state.interpretation_status = "PENDING"
            state.user_approved = False
            state.transition_to("AWAITING_CONFIRMATION", f"Interpretation pending user confirmation: {eng_spec.concise_interpretation}")
            state.add_activity(f"Interpreted Intent: {eng_spec.concise_interpretation}", level="ok")
            state.add_activity("Please confirm this interpretation to begin implementation.", level="dim")
            return False

        self.confirm_interpretation(state)
        return True

    def confirm_interpretation(self, state: ProjectState) -> bool:
        """Atomically transition state through confirmation barrier:
        AWAITING_CONFIRMATION -> CONFIRMED -> ENGINEERING_READY
        """
        state.interpretation_status = "CONFIRMED"
        state.user_approved = True
        state.transition_to("CONFIRMED", "Requirement interpretation confirmed by user.")
        state.transition_to("ENGINEERING_READY", "Execution barrier released. System ready for planning and engineering.")
        state.release_task_graph()
        state.add_activity("Requirement interpretation confirmed. Proceeding to planning & architecture.", level="ok")
        return True

    def plan_and_architect(self, state: ProjectState) -> None:
        """Phase 1B: Plan & Architect project (executes ONLY after requirement is confirmed)."""
        if not self.can_execute_plan(state) or not state.can_execute_engineering():
            state.add_activity("Planning blocked: requirement interpretation has not been confirmed.", level="bad")
            return

        def _plan_action(st: ProjectState):
            st.transition_to("PLANNING", "Requirement confirmed: designing architecture and task dependency graph...")
            st.current_phase = "PLAN"
            st.add_activity("Planner & Architect activated: generating project architecture...", level="run")

            goal_lower = st.goal.lower()
            contract = extract_architecture_contract(st.goal, selected_language=st.selected_language)
            is_fullstack_req = (
                contract.is_strict_fullstack
                or (
                    bool(re.search(r"\b(fastapi|flask|backend|api|rest\s*api|endpoint)\b", goal_lower))
                    and bool(re.search(r"\b(frontend|dashboard|html|web|interface)\b", goal_lower))
                )
            )

            raw_eng_spec = st.engineering_spec or {}
            system_prompt = (
                "You are an expert AI Software Architect and Tech Lead for SPIDY.\n"
                "Analyze the user requirement and generate a complete project architecture plan in valid JSON format.\n"
                "Output ONLY a raw JSON object with keys:\n"
                "project_name (str),\n"
                "detected_language (str e.g. HTML/CSS/JS, Python, Fullstack, JavaScript, TypeScript, Java, C++, Go, Rust),\n"
                "architecture_summary (str),\n"
                "tech_stack (list of str),\n"
                "is_fullstack (bool - True if requirement involves BOTH a backend API and a web frontend dashboard/UI),\n"
                "is_complex (bool - True if requirement needs clarification, False if straightforward),\n"
                "clarifying_questions (list of max 3 important questions if complex, otherwise empty list []),\n"
                "files (list of relative file paths to build),\n"
                "tasks (list of dicts with keys: id (str like 't-1'), title (str), phase (str: BUILD/RUN/TEST/DOCUMENT), file_path (str or null), is_required (bool))."
            )

            user_msg = (
                f"User Requirement: {st.goal}\n"
                f"Inferred Engineering Specification: {json.dumps(raw_eng_spec, indent=2)}\n"
                f"User Selected Language Preference: {st.selected_language}\n\n"
                f"{contract.to_prompt_instructions()}\n"
            )
            if is_fullstack_req or contract.is_strict_fullstack:
                user_msg += "Note: This is a FULL-STACK project requirement requiring both a backend API service and an interactive web frontend."
            elif st.selected_language != "Auto Detect":
                user_msg += f"Note: User explicitly requested {st.selected_language}. Respect this choice."

            try:
                response_raw = call_openrouter(
                    messages=[{"role": "user", "content": user_msg}],
                    system_prompt=system_prompt,
                    temperature=0.2,
                    role="planner",
                )
                plan_data = parse_json_response(response_raw)
            except Exception as exc:
                st.add_activity(f"Planner LLM call failed or provider unavailable ({exc}). Synthesizing deterministic architecture from contract...", level="run")
                plan_data = {}

            # Architecture Context Mismatch & Compliance Validation Gate (Bug 1, Bug 2)
            if not plan_data:
                is_valid_arch, mismatch_reason = False, "No plan data received from LLM provider"
                is_compliant, compliance_reason = False, "Provider unavailable or returned invalid JSON"
            else:
                is_valid_arch, mismatch_reason = validate_plan_against_requirement(st.goal, plan_data)
                is_compliant, compliance_reason = validate_plan_compliance(contract, plan_data)

            if not is_valid_arch or not is_compliant:
                reason = mismatch_reason or compliance_reason
                st.add_activity(
                    f"Architecture mismatch rejected: {reason}. Enforcing authoritative contract for {contract.project_name}...",
                    level="bad",
                )
                plan_data["project_name"] = contract.project_name
                plan_data["architecture_summary"] = (
                    f"Authoritative {contract.project_type} application architecture for {contract.project_name}. "
                    f"Frontend: {contract.frontend_framework} ({contract.frontend_language}) with {contract.frontend_tooling}; "
                    f"Backend: {contract.backend_framework} ({contract.backend_language}); "
                    f"Database: {contract.database_engine}; "
                    f"Communication: {contract.communication_protocol}."
                )
                plan_data["detected_language"] = contract.effective_language
                plan_data["is_fullstack"] = contract.is_strict_fullstack
                plan_data["files"] = generate_compliant_fullstack_files(contract)
                plan_data["tech_stack"] = [
                    contract.frontend_framework,
                    contract.frontend_language,
                    contract.backend_framework,
                    contract.database_engine,
                    contract.communication_protocol,
                ]

            st.project_spec = plan_data

            st.project_name = plan_data.get("project_name", contract.project_name) or contract.project_name
            st.detected_language = plan_data.get("detected_language", contract.effective_language)

            if is_fullstack_req or contract.is_strict_fullstack or plan_data.get("is_fullstack"):
                st.effective_language = "Fullstack"
                st.runtime_type = "fullstack"
            elif raw_eng_spec.get("application_type") == "web_3d":
                st.effective_language = "HTML/CSS/JS"
                st.runtime_type = "web_3d"
                st.project_type = "3D Web Application"
            elif st.selected_language and st.selected_language != "Auto Detect":
                st.effective_language = st.selected_language
                st.runtime_type = contract.project_type
            else:
                st.effective_language = st.detected_language
                st.runtime_type = contract.project_type

            st.architecture_summary = plan_data.get("architecture_summary", f"{contract.project_name} application architecture.")
            st.tech_stack = plan_data.get("tech_stack", [st.effective_language])
            st.clarifying_questions = [
                {"question": q, "answer": ""} for q in plan_data.get("clarifying_questions", [])
            ]

            # Populate tasks with explicit dependency graph
            st.tasks = []
            default_files = generate_compliant_fullstack_files(contract)
            raw_target_files = plan_data.get("files", default_files)
            # Filter out any placeholder paths
            target_files = [f for f in raw_target_files if not is_placeholder_path(f)[0]]
            if not target_files:
                target_files = default_files

            # 1. BUILD tasks for each file to generate (split into backend and frontend for fullstack)
            build_task_ids = []
            backend_task_ids = []
            frontend_task_ids = []

            for idx, fname in enumerate(target_files):
                tid = f"t-{idx+1}"
                is_fe = fname.endswith((".html", ".css", ".js", ".ts", ".jsx", ".tsx"))
                deps = list(backend_task_ids) if (is_fe and backend_task_ids) else []
                
                # Derive semantic task description and expected output
                if "database" in fname.lower() or "models" in fname.lower():
                    task_desc = f"Implement database schemas, connection management, and persistence layer in {fname}"
                    exp_out = f"Valid database initialization code and data models in {fname}"
                elif "router" in fname.lower() or "api" in fname.lower() or "main.py" in fname.lower():
                    task_desc = f"Implement REST API endpoints, routing, request validation, and business logic in {fname}"
                    exp_out = f"FastAPI/Flask API routes with CORS, root, and health endpoints in {fname}"
                elif "app.tsx" in fname.lower() or "main.tsx" in fname.lower() or "index.html" in fname.lower():
                    task_desc = f"Construct frontend entry point and UI layout with backend integration in {fname}"
                    exp_out = f"Functional, responsive web interface interacting with backend in {fname}"
                elif "component" in fname.lower():
                    task_desc = f"Create reusable interactive UI component in {fname}"
                    exp_out = f"Clean TypeScript/JavaScript UI component in {fname}"
                elif "requirements" in fname.lower() or "package.json" in fname.lower():
                    task_desc = f"Define third-party dependencies and build scripts in {fname}"
                    exp_out = f"Complete dependencies configuration without version conflicts in {fname}"
                else:
                    task_desc = f"Implement application module {fname} according to architecture contract"
                    exp_out = f"Production-ready source code in {fname}"

                st.add_task(
                    task_id=tid,
                    title=f"Generate {fname}",
                    phase="BUILD",
                    agent="Developer Agent",
                    file_path=fname,
                    dependencies=deps,
                    is_required=True,
                    build_id=st.build_id,
                    project_id=st.project_id,
                    description=task_desc,
                    expected_output=exp_out,
                    evidence_required="code_artifact_syntax_valid",
                )
                build_task_ids.append(tid)
                if is_fe:
                    frontend_task_ids.append(tid)
                else:
                    backend_task_ids.append(tid)

            # 2. RUN task depends on all BUILD tasks
            run_task_id = f"t-run-{len(st.tasks)+1}"
            st.add_task(
                run_task_id,
                "Launch application server process",
                "RUN",
                agent="Tester & Runner Agent",
                dependencies=list(build_task_ids),
                is_required=True,
                build_id=st.build_id,
                project_id=st.project_id,
                description="Start isolated application process, detect dynamic port, and verify TCP socket.",
                expected_output="Active runtime process with bound listening TCP port outside control range.",
                evidence_required="process_alive_and_port_listening",
            )

            # 3. TEST task depends on RUN task
            test_task_id = f"t-test-{len(st.tasks)+1}"
            st.add_task(
                test_task_id,
                "Verify application health & runtime logs",
                "TEST",
                agent="Tester & Runner Agent",
                dependencies=[run_task_id],
                is_required=True,
                build_id=st.build_id,
                project_id=st.project_id,
                description="Poll HTTP health endpoints, inspect runtime logs, and verify application responsiveness.",
                expected_output="HTTP 200 health response and valid application/API content.",
                evidence_required="http_health_check_passed",
            )

            # 4. DOCUMENT task depends on TEST task (optional, not strictly failing runtime)
            doc_task_id = f"t-doc-{len(st.tasks)+1}"
            st.add_task(
                doc_task_id,
                "Generate documentation and README",
                "DOCUMENT",
                agent="Documentation Agent",
                dependencies=[test_task_id],
                is_required=False,
                build_id=st.build_id,
                project_id=st.project_id,
                description="Generate project-specific README.md with overview, architecture, endpoints, and setup instructions.",
                expected_output="Comprehensive project-specific README.md without placeholder boilerplate.",
                evidence_required="documentation_valid",
            )

            # Calculate dynamic pre-build estimate
            est = BuildEstimator.estimate_pre_build(
                goal=st.goal,
                tech_stack=st.effective_language,
                tasks=st.tasks,
                agent_names=[t.agent_assigned for t in st.tasks if t.agent_assigned],
            )
            st.estimated_duration_str = est.range_str
            st.estimated_remaining_str = est.range_str
            st.estimated_complexity = est.complexity
            st.estimated_confidence = est.confidence

            st.current_phase = "PLAN"
            st.add_activity(f"Architecture defined for {st.project_name} ({st.effective_language}) | Est: {est.range_str}", level="ok")

            if st.project_state == "WAITING_FOR_USER":
                st.current_phase = "PLAN"
                return

            if plan_data.get("is_complex") and st.clarifying_questions:
                st.add_activity("Autonomous Tech Lead resolved architectural scope with best-practice defaults.", level="dim")
            st.user_approved = True
            st.transition_to("ARCHITECTING", "Scope validated. Architecture established.")
            st.current_phase = "ARCHITECT"
            st.add_activity("Scope validated. Proceeding to build phase.", level="ok")

        self.planner_agent.execute(state, _plan_action)

    def analyze_and_plan(self, state: ProjectState) -> None:
        """Phase 1: Discover, Plan & Architect requirements with hard confirmation gate."""
        confirmed = self.understand_requirement(state)
        if not confirmed or state.is_awaiting_confirmation():
            return
        self.plan_and_architect(state)

    def _get_workspace_dir(self) -> Optional[Path]:
        ws_root = getattr(self.workspace, "root", None)
        if isinstance(ws_root, (str, Path)):
            return Path(ws_root).resolve()
        return None

    def execute_build(self, state: ProjectState) -> None:
        """Phase 2: Build, Run, Test, Auto-Debug, Document project with strict prerequisite enforcement."""
        if state.is_awaiting_confirmation():
            state.add_activity("execute_build blocked: requirement interpretation is awaiting user confirmation.", level="bad")
            return

        if not state.build_start_time:
            state.build_start_time = time.time()

        # Step 1: BUILD Phase
        if not self.can_execute_build(state):
            state.transition_to("BLOCKED", "Prerequisites for BUILD phase not satisfied.")
            state.current_phase = "BLOCKED"
            state.active_agent = "Developer Agent"
            state.active_agent_status = "BLOCKED"
            state.current_task_description = "Build blocked: missing project requirements."
            for t in state.tasks:
                state.block_task(t.id, "Prerequisites for BUILD not satisfied.")
            return

        state.current_phase = "BUILD"
        state.transition_to("GENERATING", "Commencing project build and code generation...")
        state.project_generation_status = "GENERATING"
        state.add_activity("Commencing project build phase...", level="run")

        build_tasks = [t for t in state.tasks if t.phase == "BUILD" and (not getattr(t, "build_id", None) or t.build_id == state.build_id)]
        files_to_generate = [t.file_path for t in build_tasks if t.file_path]

        def _build_action(st: ProjectState):
            if not files_to_generate:
                files_to_generate.append("index.html" if "HTML" in st.effective_language else "app.py")

            system_prompt = (
                f"You are a principal software engineer building a project in {st.effective_language}.\n"
                f"Project Goal: {st.goal}\n"
                f"Architecture: {st.architecture_summary}\n"
                f"Tech Stack: {', '.join(st.tech_stack)}\n"
            )
            if st.clarification_answers:
                system_prompt += f"User Clarifications: {json.dumps(st.clarification_answers)}\n"

            system_prompt += (
                "Generate complete, clean, production-ready source code for the project files.\n"
                "CRITICAL GRAPHICS & QUALITY INSTRUCTION:\n"
                "If this request involves 3D, WebGL, games, statues, or 3D websites:\n"
                "- Produce high-quality, realistic, visually stunning WebGL code using Three.js (import via CDN scripts: three.min.js, OrbitControls.js, etc.).\n"
                "- Include realistic lighting (AmbientLight, DirectionalLight with castShadow=true, PointLight/SpotLight with dynamic colors).\n"
                "- Use rich materials (MeshStandardMaterial, MeshPhysicalMaterial with roughness, metalness, or detailed multi-part procedural geometry).\n"
                "- Include smooth OrbitControls for 360-degree rotation and zoom, particle background stars/dust, shadow mapping (renderer.shadowMap.enabled = true), dynamic animations, and a sleek modern HUD overlay!\n"
                "CRITICAL ARCHITECTURE INSTRUCTION:\n"
                "- If this is a Python Web API (FastAPI / Flask):\n"
                "  * Define a root endpoint `@app.get('/')` returning a welcome/status JSON payload, and a `@app.get('/health')` endpoint.\n"
                "  * Keep Pydantic models (e.g. schemas) self-contained within the file or provide `schemas.py` explicitly in your output.\n"
                "  * Provide a `requirements.txt` file listing all required third-party packages (e.g. fastapi, uvicorn, pydantic).\n\n"
                "You MUST format your output as file sections using file headers:\n\n"
                "### FILE: <filename>\n"
                "```language\n"
                "// code here\n"
                "```\n\n"
                "CRITICAL: Replace '<filename>' with the actual real file name (e.g. src/App.tsx, main.py, etc.). Never use placeholder names like 'path/to/file.ext'.\n"
                "Write FULL, fully-functional code without placeholders or 'TODO' snippets."
            )

            # Chunk file generation if many files are requested to avoid token truncation
            chunk_size = 8
            file_chunks = [files_to_generate[i:i + chunk_size] for i in range(0, len(files_to_generate), chunk_size)] if files_to_generate else [[]]

            parsed_files = {}
            for chunk in file_chunks:
                is_fe_chunk = any(f.endswith((".html", ".css", ".js", ".ts", ".jsx", ".tsx")) for f in chunk)
                is_be_chunk = any(f.endswith((".py", ".sql", "requirements.txt")) for f in chunk)

                contract_instructions = []
                if is_fe_chunk:
                    contract_instructions.append(
                        "- FRONTEND WEB CONTRACT: Generate complete, functional modern HTML5, CSS3, and JavaScript/TypeScript. "
                        "The frontend must render a clean responsive dashboard UI and include fetch() calls connecting to the backend API."
                    )
                if is_be_chunk:
                    contract_instructions.append(
                        "- BACKEND API CONTRACT: Implement FastAPI or Flask with CORS middleware (allow all origins '*'), "
                        "root endpoint '@app.get(\"/\")', health endpoint '@app.get(\"/health\")' returning {'status': 'healthy'}, "
                        "and complete REST API endpoints."
                    )

                chunk_prompt = (
                    f"Please generate the complete source code for these exact files: {', '.join(chunk)}\n"
                    f"Project Goal: {st.requirements}\n"
                    f"Architecture: {st.architecture_summary}\n"
                    + ("\n".join(contract_instructions) + "\n" if contract_instructions else "")
                    + "Produce full, functional code for EACH file using '### FILE: <filename>' with the exact filename from the list above. Do not omit any requested file."
                )
                try:
                    raw_code = call_openrouter(
                        messages=[{"role": "user", "content": chunk_prompt}],
                        system_prompt=system_prompt,
                        temperature=0.2,
                        role="coder",
                    )
                    def_fname = chunk[0] if len(chunk) == 1 else None
                    batch_parsed = parse_multi_file_response(raw_code, default_filename=def_fname)
                    if "main_output" in batch_parsed:
                        unmatched = [f for f in chunk if f not in batch_parsed and not any(k.endswith(f) or f.endswith(k) for k in batch_parsed)]
                        if len(unmatched) == 1:
                            batch_parsed[unmatched[0]] = batch_parsed.pop("main_output")
                        else:
                            content = batch_parsed["main_output"]
                            matched_cand = None
                            for f in unmatched:
                                if f.endswith((".js", ".ts", ".jsx", ".tsx")) and any(kw in content for kw in ["function", "const ", "let ", "document."]):
                                    matched_cand = f
                                    break
                                elif f.endswith(".html") and ("<html" in content or "<!doctype" in content.lower()):
                                    matched_cand = f
                                    break
                                elif f.endswith(".css") and ("{" in content and "}" in content):
                                    matched_cand = f
                                    break
                                elif f.endswith(".py") and any(kw in content for kw in ["def ", "import ", "from "]):
                                    matched_cand = f
                                    break
                                elif f.endswith(".md") and ("#" in content):
                                    matched_cand = f
                                    break
                            if matched_cand:
                                batch_parsed[matched_cand] = batch_parsed.pop("main_output")
                            else:
                                batch_parsed.pop("main_output", None)
                    parsed_files.update(batch_parsed)
                except Exception as exc:
                    st.add_activity(f"Error generating code chunk: {exc}", level="bad")

                # Targeted recovery for any file in chunk that was missed by multi-file parser
                for req_file in chunk:
                    matched_req = req_file in parsed_files or any(k.endswith(req_file) or req_file.endswith(k) for k in parsed_files)
                    if not matched_req:
                        st.add_activity(f"Targeted recovery generating missing file: {req_file}...", level="run")
                        single_prompt = (
                            f"Generate complete, working production code for ONLY this specific file: {req_file}\n"
                            f"Project Goal: {st.goal}\n"
                            f"Architecture: {st.architecture_summary}\n"
                            f"Stack: {st.effective_language}\n"
                            f"Output using: ### FILE: {req_file}\n```\ncode\n```"
                        )
                        try:
                            single_raw = call_openrouter(
                                messages=[{"role": "user", "content": single_prompt}],
                                system_prompt="You are a senior principal engineer. Return the complete code for the requested file.",
                                temperature=0.2,
                                role="coder",
                            )
                            single_parsed = parse_multi_file_response(single_raw, default_filename=req_file)
                            if req_file in single_parsed:
                                parsed_files[req_file] = single_parsed[req_file]
                            elif single_parsed:
                                matched_k = next((k for k in single_parsed if k.endswith(req_file) or req_file.endswith(k)), None)
                                if matched_k:
                                    parsed_files[req_file] = single_parsed[matched_k]
                                else:
                                    parsed_files[req_file] = next(iter(single_parsed.values()))
                            elif single_raw.strip():
                                clean_code = clean_code_block(single_raw)
                                if clean_code:
                                    parsed_files[req_file] = clean_code
                        except Exception as exc:
                            st.add_activity(f"Targeted generation failed for {req_file}: {exc}", level="bad")

            # 1. Write each unique file once and emit an accurate creation/update event
            written_files = set()
            for fpath, fcontent in parsed_files.items():
                if fpath == "main_output" or is_placeholder_path(fpath)[0]:
                    continue
                if fpath not in written_files:
                    is_new = True
                    if hasattr(self.workspace, "file_exists"):
                        is_new = not self.workspace.file_exists(fpath)
                    elif hasattr(self.workspace, "list_files"):
                        is_new = fpath not in self.workspace.list_files()
                    self.workspace.write_file(fpath, fcontent)
                    st.files[fpath] = fcontent
                    written_files.add(fpath)
                    action_label = "File created" if is_new else "File updated"
                    st.add_activity(f"{action_label}: {fpath}", level="ok")

            # 2. Update task completion status with artifact validation
            ws_dir = self._get_workspace_dir()
            for task in build_tasks:
                st.set_active_task(task.id)
                target_file = task.file_path
                matched = False
                matched_key = None
                if target_file:
                    if target_file in st.files:
                        matched = True
                        matched_key = target_file
                    else:
                        matched_key = next((k for k in st.files if k.endswith(target_file) or target_file.endswith(k)), None)
                        if matched_key:
                            matched = True
                elif written_files:
                    matched = True

                if matched:
                    content_to_check = st.files.get(matched_key, "") if matched_key else ""
                    is_valid, val_reason, val_details = validate_artifact(
                        file_path=target_file or "artifact",
                        content=content_to_check,
                        workspace_dir=ws_dir,
                    )
                    if is_valid:
                        agent_res = AgentResult(
                            status="SUCCESS",
                            task_id=task.id,
                            project_id=st.project_id,
                            build_id=st.build_id,
                            success=True,
                            artifact_path=target_file,
                            provider="ModelRouter",
                            validation_result=val_details,
                        )
                        st.complete_task(task.id, agent_result=agent_res)
                        counts = st.task_counts
                        est_pre = BuildEstimator.estimate_pre_build(st.goal, st.effective_language, st.tasks)
                        st.estimated_remaining_str = BuildEstimator.calculate_remaining_estimate(
                            pre_build=est_pre,
                            elapsed_seconds=st.elapsed_seconds,
                            completed_tasks=counts["completed"],
                            total_tasks=counts["total"],
                        )
                    else:
                        st.add_activity(f"Artifact validation failed for {target_file}: {val_reason}", level="bad")
                        st.fail_task(task.id, f"Artifact invalid: {val_reason}")
                else:
                    st.add_activity(f"Failed to generate code for {target_file or task.id}", level="bad")
                    st.fail_task(task.id, f"Code generation missed {target_file}")

        self.developer_agent.execute(state, _build_action)

        # BOUNDED TASK RECOVERY LOOP: Up to 3 attempts per failed build task
        failed_build_tasks = [
            t for t in build_tasks
            if t.status in ("FAILED", "RECOVERING", "RETRYING")
            and (not getattr(t, "build_id", None) or t.build_id == state.build_id)
        ]

        if failed_build_tasks:
            state.add_activity(
                f"Commencing bounded recovery for {len(failed_build_tasks)} task(s)...",
                level="run",
            )
            ws_dir = self._get_workspace_dir()

            for task in failed_build_tasks:
                target_file = task.file_path or f"{task.id}.ext"
                state.recover_task(task.id, f"Artifact missing or invalid: {target_file}")

                for attempt in range(1, 4):
                    state.retry_task(task.id, attempt)
                    last_err = task.error or "Artifact validation failed or file was not generated."
                    recovery_prompt = (
                        f"RECOVERY ATTEMPT {attempt}/3 for {target_file}:\n"
                        f"Project: {state.project_name}\n"
                        f"Goal: {state.goal}\n"
                        f"Architecture: {state.architecture_summary}\n"
                        f"Language / Stack: {state.effective_language}\n"
                        f"PREVIOUS FAILURE EVIDENCE: {last_err}\n"
                        f"Generate complete, fully functional, production-ready code for ONLY this file: {target_file}\n"
                        f"Ensure the issue described in the failure evidence above is resolved.\n"
                        f"Do NOT omit any code. Output using:\n"
                        f"### FILE: {target_file}\n```\ncode\n```"
                    )

                    try:
                        raw_recovery = call_openrouter(
                            messages=[{"role": "user", "content": recovery_prompt}],
                            system_prompt="You are a senior principal engineer executing automated artifact recovery. Output complete, working code.",
                            temperature=0.2,
                            role="coder",
                        )

                        parsed_rec = parse_multi_file_response(raw_recovery, default_filename=target_file)
                        rec_content = parsed_rec.get(target_file)
                        if not rec_content:
                            matched_rec_k = next((k for k in parsed_rec if k.endswith(target_file) or target_file.endswith(k)), None)
                            if matched_rec_k:
                                rec_content = parsed_rec[matched_rec_k]
                            elif raw_recovery.strip():
                                rec_content = clean_code_block(raw_recovery)

                        if rec_content:
                            is_valid, val_reason, val_details = validate_artifact(
                                file_path=target_file,
                                content=rec_content,
                                workspace_dir=ws_dir,
                            )
                            if is_valid:
                                self.workspace.write_file(target_file, rec_content)
                                state.files[target_file] = rec_content
                                state.record_success("artifact_generation", target_file)
                                agent_res = AgentResult(
                                    status="RECOVERED",
                                    task_id=task.id,
                                    project_id=state.project_id,
                                    build_id=state.build_id,
                                    success=True,
                                    artifact_path=target_file,
                                    provider="OpenRouter" if getattr(self, "openrouter_used", False) else "ModelRouter",
                                    recovery_attempt=attempt,
                                    validation_result=val_details,
                                )
                                state.complete_task(task.id, result=f"Recovered on attempt {attempt}", agent_result=agent_res)
                                state.add_activity(f"{target_file} validated successfully ({val_details.get('size_bytes', 0)} bytes)", level="ok")
                                state.add_activity(f"Task {task.id} ({task.title}) RECOVERED (Attempt {attempt}/3)", level="ok")
                                break
                            else:
                                state.add_activity(f"Recovery attempt {attempt}/3 for {target_file} validation failed: {val_reason}", level="bad")
                                task.error = f"Validation failed: {val_reason}"
                                is_loop = state.record_failure("artifact_generation", "VALIDATION_FAILURE", target_file, val_reason, phase="BUILD")
                                if is_loop:
                                    state.add_activity(f"Halting recovery retries for {target_file}: repeated identical validation failure.", level="bad")
                                    break
                        else:
                            state.add_activity(f"Recovery attempt {attempt}/3 for {target_file} produced empty response", level="bad")
                            is_loop = state.record_failure("artifact_generation", "EMPTY_RESPONSE", target_file, "empty response", phase="BUILD")
                            if is_loop:
                                state.add_activity(f"Halting recovery retries for {target_file}: repeated empty response.", level="bad")
                                break

                    except Exception as rec_exc:
                        state.add_activity(f"Recovery attempt {attempt}/3 failed for {target_file}: {rec_exc}", level="bad")
                        is_loop = state.record_failure("artifact_generation", "EXCEPTION", target_file, str(rec_exc), phase="BUILD")
                        if is_loop:
                            state.add_activity(f"Halting recovery retries for {target_file}: repeated exception.", level="bad")
                            break

                if task.status != "SUCCESS":
                    agent_res = AgentResult(
                        status="FAILED",
                        task_id=task.id,
                        project_id=state.project_id,
                        build_id=state.build_id,
                        success=False,
                        artifact_path=target_file,
                        error=f"Exhausted recovery attempts or loop detected for {target_file}",
                        recovery_attempt=attempt,
                    )
                    state.fail_task(task.id, f"Exhausted recovery attempts for {target_file}", agent_result=agent_res)

            # Re-evaluate task dependency graph now that recovery completed
            state.recalculate_task_graph()

        # GENERATION GATE: Verify workspace contains files and no required build tasks failed
        workspace_files = self.workspace.list_files()
        has_failed_required = state.has_failed_required_tasks(phase="BUILD")
        if not workspace_files or len(workspace_files) == 0 or has_failed_required:
            state.is_project_generated = False
            state.project_generation_status = "GENERATION_FAILED"
            state.failure_type = "PROJECT_GENERATION_FAILURE"
            failed_tasks = [t.title for t in state.tasks if t.phase == "BUILD" and t.status == "FAILED" and getattr(t, "is_required", True)]
            if not workspace_files or len(workspace_files) == 0:
                state.failure_classification = "PRECONDITION_FAILURE"
                state.failure_reason = "No files were generated in workspace."
                state.current_phase = "BLOCKED"
                state.active_agent = "Developer Agent"
                state.active_agent_status = "BLOCKED"
                state.current_task_description = "Project generation produced no files. Downstream execution blocked."
                state.transition_to("BLOCKED", "Workspace is empty after build phase")
            else:
                state.failure_classification = "REQUIRED_FILES_MISSING"
                state.failure_reason = f"Required build tasks failed: {', '.join(failed_tasks)}" if failed_tasks else "Required files missing."
                state.current_phase = "FAILED"
                state.active_agent = "Developer Agent"
                state.active_agent_status = "FAILURE"
                state.current_task_description = f"Project generation incomplete: {state.failure_reason}"
                state.transition_to("FAILED", state.failure_reason)

            # Block all downstream tasks
            for t in state.tasks:
                if t.phase in ("RUN", "TEST", "DEBUG", "DOCUMENT", "REVIEW"):
                    if not workspace_files or len(workspace_files) == 0:
                        state.block_task(t.id, "Precondition failed: Project was not generated (empty workspace).")
                    else:
                        state.block_task(t.id, f"Blocked: Generation failed ({state.failure_reason}).")

            state.add_activity(f"Generation Gate FAILED: {state.failure_reason}. Halting pipeline.", level="bad")
            return

        # Passed Generation Gate
        state.is_project_generated = True
        state.project_generation_status = "GENERATED"
        state.verification_gates["build"] = True
        state.transition_to("GENERATED", "Source files successfully generated.")

        # ARCHITECTURE COMPLIANCE GATE: Enforce contracted layers (React/Vite, FastAPI, SQLite)
        contract = getattr(state, "architecture_contract", None)
        if contract and getattr(contract, "is_strict_fullstack", False):
            is_compliant, missing_layers, compliance_reason = validate_architecture_compliance(
                contract,
                state.files,
                list_files_fn=self.workspace.list_files if hasattr(self.workspace, "list_files") else None,
            )
            if not is_compliant:
                state.add_activity(
                    f"Architecture compliance check failed: {compliance_reason}. Attempting recovery of missing layers...",
                    level="bad",
                )
                mandatory_files = generate_compliant_fullstack_files(contract)
                for missing_file in mandatory_files:
                    if missing_file not in state.files and not any(k.endswith(missing_file) for k in state.files):
                        state.add_activity(f"Attempting recovery for architectural file: {missing_file}", level="run")
                        self._attempt_single_file_recovery(state, None, missing_file)

                # Re-verify architecture compliance after recovery
                is_compliant, missing_layers, compliance_reason = validate_architecture_compliance(
                    contract,
                    state.files,
                    list_files_fn=self.workspace.list_files if hasattr(self.workspace, "list_files") else None,
                )
                if not is_compliant:
                    state.failure_classification = "ARCHITECTURE_NON_COMPLIANT"
                    state.failure_reason = f"Architecture contract violated: {compliance_reason}"
                    state.current_phase = "FAILED"
                    state.active_agent = "Developer Agent"
                    state.active_agent_status = "FAILURE"
                    state.current_task_description = f"Build failed architecture compliance: {state.failure_reason}"
                    state.transition_to("FAILED", state.failure_reason)
                    for t in state.tasks:
                        if t.phase in ("RUN", "TEST", "DEBUG", "DOCUMENT", "REVIEW"):
                            state.block_task(t.id, f"Blocked: Architecture contract violation ({state.failure_reason})")
                    state.add_activity(f"Architecture Compliance Gate FAILED: {state.failure_reason}. Halting pipeline.", level="bad")
                    return
                else:
                    state.add_activity("Architecture compliance verified after recovery.", level="ok")

        # Step 2: RUN Phase
        detector = getattr(self.runner, "detector", None) or getattr(self, "detector", None) or EnvironmentDetector()
        env_config = detector.detect(self.workspace, override_language=state.selected_language)
        state.project_type = env_config.get("project_type", state.project_type)
        state.runtime_command = " ".join(env_config["command"]) if env_config.get("command") else ""
        state.runtime_cwd = env_config.get("cwd", str(getattr(self.workspace, "root", ".")))

        if not self.can_execute_run(state):
            state.current_phase = "BLOCKED"
            state.active_agent = "Tester & Runner Agent"
            state.active_agent_status = "BLOCKED"
            state.transition_to("BLOCKED", "Preconditions for RUN phase not satisfied.")
            for t in state.tasks:
                if t.phase in ("RUN", "TEST", "DEBUG", "DOCUMENT", "REVIEW"):
                    state.block_task(t.id, "Preconditions for RUN not satisfied.")
            return

        state.current_phase = "RUN"
        state.transition_to("RUNNING", "Launching application process via Project Runner...")
        state.add_activity("Launching application process via Project Runner...", level="run")

        run_tasks = [t for t in state.tasks if t.phase == "RUN" and (not getattr(t, "build_id", None) or t.build_id == state.build_id)]
        if not run_tasks:
            t_id = f"t-run-{len(state.tasks)+1}"
            state.add_task(t_id, "Launch application server process", "RUN", agent="Tester & Runner Agent", build_id=state.build_id, project_id=state.project_id)
            run_tasks = [t for t in state.tasks if t.id == t_id]

        def _run_action(st: ProjectState):
            for task in run_tasks:
                if not st.is_task_ready(task):
                    st.block_task(task.id, "Prerequisite BUILD tasks not completed successfully.")
                    continue
                st.set_active_task(task.id)
                success = self.runner.run(st)
                if success:
                    task.evidence_collected = {
                        "pid": st.runtime_pid,
                        "port": st.runtime_port,
                        "url": st.runtime_url,
                        "status": st.runtime_status,
                    }
                    st.complete_task(task.id)
                elif st.failure_classification == "PRECONDITION_FAILURE":
                    st.block_task(task.id, f"Precondition failed: {st.failure_reason}")
                else:
                    st.failure_classification = st.failure_classification or "RUNTIME_STARTUP_FAILURE"
                    st.fail_task(task.id, f"Process startup or runtime verification failed: {st.failure_reason or st.failure_classification}")

        self.tester_agent.execute(state, _run_action)

        # Step 3: TEST & AUTO-DEBUG Phase
        if not self.can_execute_test(state):
            state.current_phase = "BLOCKED"
            state.active_agent = "Tester & Runner Agent"
            state.active_agent_status = "BLOCKED"
            state.transition_to("BLOCKED", "Preconditions for TEST phase not satisfied.")
            for t in state.tasks:
                if t.phase in ("TEST", "DEBUG", "DOCUMENT", "REVIEW"):
                    state.block_task(t.id, "Precondition failed: project not testable or not running.")
            return

        if state.failure_classification == "PRECONDITION_FAILURE":
            # Precondition failure: do not invoke Debugger Agent on code
            state.current_phase = "BLOCKED"
            state.active_agent_status = "BLOCKED"
            state.transition_to("BLOCKED", f"Blocked by precondition failure: {state.failure_reason}")
            for t in state.tasks:
                if t.phase in ("TEST", "DEBUG", "DOCUMENT", "REVIEW"):
                    state.block_task(t.id, f"Blocked by precondition failure: {state.failure_reason}")
            return

        state.current_phase = "TEST"
        state.transition_to("TESTING", "Running health check and inspecting runtime logs...")
        state.add_activity("Running health check and inspecting runtime logs...", level="run")

        test_tasks = [t for t in state.tasks if t.phase in ("TEST", "DEBUG") and (not getattr(t, "build_id", None) or t.build_id == state.build_id)]

        def _test_debug_action(st: ProjectState):
            for task in test_tasks:
                if not st.is_task_ready(task):
                    st.block_task(task.id, "Prerequisite RUN task not completed successfully.")
                    continue

                st.set_active_task(task.id)

                # Syntax verification for Python files
                has_syntax_err = False
                for fname, content in list(st.files.items()):
                    if fname.endswith(".py"):
                        try:
                            compile(content, fname, "exec")
                            st.add_activity(f"Syntax check PASSED: {fname}", level="ok")
                        except SyntaxError as syn_err:
                            has_syntax_err = True
                            st.add_activity(f"Syntax error in {fname}: {syn_err}. Activating Debugger Agent...", level="bad")
                            if self.can_execute_debug(st):
                                st.current_phase = "DEBUG"
                                st.transition_to("DEBUGGING", f"Syntax error in {fname}")

                                fix_prompt = f"Fix syntax error in {fname}:\nError: {syn_err}\nCode:\n{content}"
                                fixed = call_openrouter(
                                    messages=[{"role": "user", "content": fix_prompt}],
                                    system_prompt="You are an expert debugger. Return ONLY corrected code.",
                                    temperature=0.1,
                                    role="debugger",
                                )
                                cleaned_fixed = clean_code_block(fixed, "python")
                                self.workspace.write_file(fname, cleaned_fixed)
                                st.files[fname] = cleaned_fixed
                                st.add_activity(f"Debugger Agent fixed syntax in {fname}", level="ok")

                # Auto-recovery if process failed or application verification failed (and preconditions were satisfied)
                is_failed = (st.runtime_status == "FAILED" or has_syntax_err or not st.is_app_verified or not st.project_success)
                if is_failed and self.can_execute_debug(st):
                    st.current_phase = "DEBUG"
                    st.transition_to("DEBUGGING", "Runtime or application verification failure detected; attempting repair")
                    st.add_activity("Runtime/verification failure detected. Debugger Agent repairing workspace...", level="bad")

                    logs = ""
                    pm = getattr(self.runner, "process_manager", None)
                    if pm and hasattr(pm, "get_logs_text"):
                        try:
                            logs = pm.get_logs_text() or ""
                        except Exception:
                            logs = getattr(st, "runtime_logs", "") or ""
                    else:
                        logs = getattr(st, "runtime_logs", "") or ""

                    browser_errs = [err for err in st.errors if "Browser" in err or "Console" in err or "Exception" in err or "Canvas" in err]
                    browser_err_text = "\n".join(browser_errs)
                    
                    # Target specific file mentioned in traceback, browser errors, or failure reason
                    targeted_file = None
                    all_err_text = f"{st.failure_reason or ''}\n{browser_err_text}\n{logs}"
                    for fname in st.files.keys():
                        base = fname.split("/")[-1]
                        if fname in all_err_text or (len(base) > 3 and base in all_err_text):
                            targeted_file = fname
                            break

                    if not targeted_file:
                        file_match = re.search(r'File "([^"]+\.[a-zA-Z0-9]+)"', logs) or re.search(r"File '([^']+\.[a-zA-Z0-9]+)'", logs)
                        if file_match:
                            cand = file_match.group(1).replace("\\", "/")
                            for f in st.files.keys():
                                if f in cand or cand.endswith(f):
                                    targeted_file = f
                                    break

                    if not targeted_file:
                        if st.is_web_project or getattr(st, "runtime_type", "") in ("web", "web_3d", "fullstack"):
                            targeted_file = next(
                                (f for f in st.files.keys() if f in ("index.html", "src/App.tsx", "src/App.jsx", "main.js", "script.js", "app.js")),
                                list(st.files.keys())[0] if st.files else "index.html"
                            )
                        else:
                            targeted_file = next((f for f in st.files.keys() if "main" in f or "app" in f), list(st.files.keys())[0] if st.files else "main.py")

                    relevant_files_text = ""
                    code_exts = (".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".json", "requirements.txt", "package.json")
                    for f_name, f_content in st.files.items():
                        if f_name == targeted_file or any(f_name.endswith(ext) for ext in code_exts):
                            relevant_files_text += f"\n### FILE: {f_name}\n```\n{f_content[:2500]}\n```\n"

                    debug_prompt = (
                        f"The project encountered a runtime or application verification failure.\n"
                        f"Failure Classification: {st.failure_classification}\n"
                        f"Failure Reason: {st.failure_reason}\n"
                        + (f"Browser Verification Errors:\n{browser_err_text}\n\n" if browser_err_text else "")
                        + f"Targeted File with error: {targeted_file}\n\n"
                        f"Runtime Logs:\n{logs[-2500:]}\n\n"
                        f"Relevant Workspace Files:\n{relevant_files_text}\n\n"
                        f"Project Architecture: {st.architecture_summary}\n"
                        "Fix the root cause and output the corrected file(s) in ### FILE: path/to/file format."
                    )

                    fixed_raw = call_openrouter(
                        messages=[{"role": "user", "content": debug_prompt}],
                        system_prompt="You are a senior debugger. Output corrected files with full working code.",
                        temperature=0.1,
                        role="debugger",
                    )
                    fixed_files = parse_multi_file_response(fixed_raw, default_filename=targeted_file)
                    for path, text in fixed_files.items():
                        if path in st.files or len(fixed_files) == 1:
                            target = path if path in st.files else targeted_file
                            self.workspace.write_file(target, text)
                            st.files[target] = text
                            st.add_activity(f"Applied debug fix to {target}", level="ok")

                    # Re-run after debug
                    st.add_activity("Re-starting process after applying debug fix...", level="run")
                    re_success = self.runner.restart(st)
                    if re_success and st.project_success and (not st.is_web_project or st.is_app_verified):
                        task.evidence_collected = {
                            "recovered": True,
                            "runtime_status": st.runtime_status,
                            "gates": dict(st.verification_gates),
                        }
                        st.complete_task(task.id)
                    else:
                        st.failure_classification = st.failure_classification or "DEBUG_REPAIR_FAILURE"
                        st.fail_task(task.id, f"Verification failed after debug: {st.failure_reason or st.failure_classification}")
                elif st.runtime_status == "FAILED" or not st.is_app_verified or not st.project_success:
                    st.block_task(task.id, f"Debugging blocked: {st.failure_reason or 'precondition failure'}")
                else:
                    if st.project_success and (not st.is_web_project or st.is_app_verified):
                        task.evidence_collected = {
                            "runtime_status": st.runtime_status,
                            "gates": dict(st.verification_gates),
                            "targets": list(st.runtime_targets),
                        }
                        st.complete_task(task.id)
                    else:
                        st.failure_classification = st.failure_classification or "RUNTIME_VERIFICATION_FAILURE"
                        st.fail_task(task.id, f"Runtime verification failed: {st.failure_reason or st.failure_classification}")

        self.debugger_agent.execute(state, _test_debug_action)

        # Step 4: DOCUMENT & REVIEW Phase
        if not state.is_project_generated:
            for t in state.tasks:
                if t.phase in ("REVIEW", "DOCUMENT"):
                    state.block_task(t.id, "Precondition failed: Project was not generated.")
            return

        state.current_phase = "REVIEW"
        state.transition_to("DOCUMENTING", "Generating documentation...")
        state.add_activity("Generating project documentation and README.md...", level="run")

        doc_tasks = [t for t in state.tasks if t.phase in ("REVIEW", "DOCUMENT") and (not getattr(t, "build_id", None) or t.build_id == state.build_id)]

        def _doc_action(st: ProjectState):
            for task in doc_tasks:
                st.set_active_task(task.id)

            readme_text = st.files.get("README.md", "")
            is_valid_readme, readme_err = validate_readme_content(readme_text, st.project_name or st.goal)
            if not is_valid_readme or "README.md" not in st.files:
                readme_prompt = (
                    f"Write a comprehensive, project-specific README.md for '{st.project_name}'.\n"
                    f"Project Goal: {st.goal}\n"
                    f"Tech Stack: {', '.join(st.tech_stack) if st.tech_stack else st.effective_language}\n"
                    f"Files in project: {list(st.files.keys())}\n"
                    "Requirements for README.md:\n"
                    f"1. Must clearly describe '{st.project_name}' and its core functionality.\n"
                    "2. Must document tech stack, architecture, API endpoints, and running instructions.\n"
                    "3. DO NOT output generic boilerplate like 'Fork the repository', 'Create a feature branch', or 'MIT License' without context.\n"
                )
                try:
                    readme_content = call_openrouter(
                        messages=[{"role": "user", "content": readme_prompt}],
                        system_prompt="You are a senior technical writer. Output raw markdown for project README.md.",
                        temperature=0.2,
                        role="general",
                    )
                    cleaned_readme = clean_code_block(readme_content, "markdown")
                    val_ok, _ = validate_readme_content(cleaned_readme, st.project_name or st.goal)
                    if val_ok:
                        self.workspace.write_file("README.md", cleaned_readme)
                        st.files["README.md"] = cleaned_readme
                        st.add_activity("Generated project-specific README.md documentation", level="ok")
                    else:
                        # Fallback to structured project-specific template
                        fallback_readme = (
                            f"# {st.project_name}\n\n"
                            f"## Overview\n{st.goal}\n\n"
                            f"## Tech Stack\n{', '.join(st.tech_stack) if st.tech_stack else st.effective_language}\n\n"
                            f"## Features & Architecture\n- Designed with modular frontend and backend separation.\n"
                            f"- Files implemented:\n" + "\n".join(f"  - `{f}`" for f in st.files.keys()) + "\n\n"
                            f"## Running the Project\nExecute application runtime command or scripts.\n"
                        )
                        self.workspace.write_file("README.md", fallback_readme)
                        st.files["README.md"] = fallback_readme
                        st.add_activity("Generated structured project-specific README.md", level="ok")
                except Exception as exc:
                    st.add_activity(f"Failed to generate README: {exc}", level="dim")

            for t in doc_tasks:
                st.complete_task(t.id)

            if "README.md" in st.files or (hasattr(self.workspace, "file_exists") and self.workspace.file_exists("README.md")):
                for t in st.tasks:
                    if t.file_path and "readme" in t.file_path.lower() and t.status != "SUCCESS":
                        st.complete_task(t.id, result="Documented in README.md")

            st.recalculate_task_graph()

        self.documentation_agent.execute(state, _doc_action)

        # Step 5: REVIEW Phase
        ws_dir = self._get_workspace_dir()
        review_verdict = self.reviewer_agent.review(state, ws_dir)

        # Bounded recovery loop if Reviewer detected issues (max 3 retries)
        while review_verdict.verdict == "NEEDS_RECOVERY" and state.recovery_attempts < 3:
            issues_str = "; ".join(review_verdict.issues) if review_verdict.issues else "Unknown issue"
            is_loop = state.record_failure("reviewer_audit", "NEEDS_RECOVERY", "workspace", issues_str, phase="REVIEW")
            if is_loop:
                state.add_activity("Halting reviewer recovery: identical reviewer issues repeated without progress.", level="bad")
                break

            state.recovery_attempts += 1
            state.add_activity(
                f"Reviewer identified issues: {issues_str}. Commencing bounded recovery (Attempt {state.recovery_attempts}/3)...",
                level="run",
            )
            self._attempt_recovery(state, review_verdict)
            review_verdict = self.reviewer_agent.review(state, ws_dir)
            if review_verdict.verdict == "PASS":
                state.record_success("reviewer_audit", "workspace")

        # Finalize: NEVER FAKE SUCCESS! Check all verification gates
        has_failed_required = state.has_failed_required_tasks()
        reviewer_passed = (review_verdict.verdict == "PASS")
        if ws_dir:
            asset_ok, missing_assets = PreviewManager.verify_referenced_assets(ws_dir)
        else:
            asset_ok, missing_assets = True, []

        # Authoritative multi-gate evaluation
        build_gate = GateEvaluator.evaluate_build(ws_dir, state.files, getattr(state, "architecture_contract", None))
        state.verification_gates["build"] = build_gate.passed

        is_verified = (
            state.is_project_generated
            and state.project_success
            and (state.runtime_status in ("RUNNING", "STOPPED") if not state.is_web_project else state.runtime_status == "RUNNING")
            and (not state.is_web_project or state.is_app_verified)
            and not has_failed_required
            and reviewer_passed
            and asset_ok
            and build_gate.passed
        )

        if is_verified:
            state.current_phase = "COMPLETE"
            state.transition_to("SUCCESS", "All verification gates and reviewer audit passed")
            state.active_agent = "Orchestrator"
            state.active_agent_status = "SUCCESS"
            state.current_task_description = "All pipeline stages and project verification completed successfully."
            state.add_activity("Project build, execution & verification COMPLETE!", level="ok")
        elif state.project_state == "BLOCKED" or state.failure_classification == "PRECONDITION_FAILURE":
            state.current_phase = "BLOCKED"
            state.transition_to("BLOCKED", "Execution halted due to blocked preconditions")
            state.active_agent_status = "BLOCKED"
            failure_msg = state.failure_reason or "Pipeline prerequisites not satisfied"
            state.current_task_description = f"Pipeline BLOCKED: {failure_msg}"
            state.add_activity(f"Pipeline BLOCKED: {failure_msg}", level="dim")
        else:
            state.current_phase = "FAILED"
            state.transition_to("FAILED", "Verification failed")
            state.active_agent = "Orchestrator"
            state.active_agent_status = "FAILURE"
            failure_reasons = []
            if has_failed_required:
                failure_reasons.append("required task failure")
            if not reviewer_passed:
                failure_reasons.append(f"reviewer issues: {', '.join(review_verdict.issues[:2])}")
            if not asset_ok:
                failure_reasons.append(f"missing referenced assets: {', '.join(missing_assets[:2])}")
            if not state.project_success:
                failure_reasons.append(state.failure_reason or f"runtime status is {state.runtime_status}")
            failure_msg = "; ".join(failure_reasons) if failure_reasons else (state.failure_reason or f"Runtime status is {state.runtime_status}")
            state.failure_reason = failure_msg
            state.failure_classification = state.failure_classification or "VERIFICATION_FAILURE"
            state.current_task_description = f"Project verification FAILED: {failure_msg}"
            state.add_activity(f"Pipeline execution halted with verification FAILURE: {failure_msg}", level="bad")

        state.build_end_time = time.time()
        state.actual_duration_str = BuildEstimator.format_actual(state.elapsed_seconds)
        try:
            HistoryManager().record_project(
                project_name=state.project_name or "SPIDY Project",
                goal=state.goal,
                tech_stack=", ".join(state.tech_stack) if state.tech_stack else state.effective_language,
                status="COMPLETED" if is_verified else ("BLOCKED" if state.current_phase == "BLOCKED" else "FAILED"),
                duration_seconds=state.elapsed_seconds,
                duration_str=state.actual_duration_str,
                estimate_range=state.estimated_duration_str,
                file_count=len(state.files),
            )
        except Exception:
            pass

    def _attempt_single_file_recovery(self, state: ProjectState, task_id: Optional[str], target_file: str) -> bool:
        """Attempt targeted recovery for a single file, validating and writing to workspace."""
        if not target_file or is_placeholder_path(target_file)[0]:
            return False
        ws_dir = self._get_workspace_dir()
        prompt = (
            f"Generate complete, fully functional, production-ready code for ONLY this file: {target_file}\n"
            f"Project: {state.project_name}\n"
            f"Goal: {state.goal}\n"
            f"Architecture: {state.architecture_summary}\n"
            f"Language / Stack: {state.effective_language}\n"
            f"Do NOT omit any code. Output using:\n"
            f"### FILE: {target_file}\n```\ncode\n```"
        )
        try:
            raw = call_openrouter(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a senior principal engineer executing automated artifact recovery. Output complete, working code.",
                temperature=0.2,
                role="coder",
            )
            parsed = parse_multi_file_response(raw, default_filename=target_file)
            content = parsed.get(target_file)
            if not content:
                matched_k = next((k for k in parsed if k.endswith(target_file) or target_file.endswith(k)), None)
                if matched_k:
                    content = parsed[matched_k]
                elif raw.strip():
                    content = clean_code_block(raw)

            if content:
                is_valid, val_reason, val_details = validate_artifact(
                    file_path=target_file,
                    content=content,
                    workspace_dir=ws_dir,
                )
                if is_valid:
                    self.workspace.write_file(target_file, content)
                    state.files[target_file] = content
                    if task_id:
                        agent_res = AgentResult(
                            status="RECOVERED",
                            task_id=task_id,
                            project_id=state.project_id,
                            build_id=state.build_id,
                            success=True,
                            artifact_path=target_file,
                            validation_result=val_details,
                        )
                        state.complete_task(task_id, result="Recovered missing file", agent_result=agent_res)
                    state.add_activity(f"Recovered file {target_file} ({val_details.get('size_bytes', 0)} bytes)", level="ok")
                    return True
                else:
                    state.add_activity(f"Recovery validation failed for {target_file}: {val_reason}", level="bad")
            else:
                state.add_activity(f"Recovery produced empty code for {target_file}", level="bad")
        except Exception as exc:
            state.add_activity(f"Recovery attempt failed for {target_file}: {exc}", level="bad")
        return False

    def _attempt_recovery(self, state: ProjectState, verdict: ReviewVerdict) -> None:
        """Attempt bounded recovery for issues reported by Reviewer."""
        ws_dir = self._get_workspace_dir()
        if not ws_dir:
            return
        asset_ok, missing_assets = PreviewManager.verify_referenced_assets(ws_dir)

        # 1. Contextual Recovery: Missing files and assets
        missing_to_recover = list(missing_assets)
        failed_tasks = [t for t in state.tasks if t.status == "FAILED" and t.file_path and (not getattr(t, "build_id", None) or t.build_id == state.build_id)]
        for ft in failed_tasks:
            if ft.file_path and ft.file_path not in missing_to_recover:
                missing_to_recover.append(ft.file_path)

        if missing_to_recover:
            state.add_activity(f"Recovery: Generating missing required files: {', '.join(missing_to_recover)}", level="run")
            for ma in missing_to_recover:
                asset_name = ma.split("->")[-1].strip() if "->" in ma else ma.strip()
                if is_placeholder_path(asset_name)[0]:
                    continue
                self._attempt_single_file_recovery(state, None, asset_name)

            state.recalculate_task_graph()

        # 2. Contextual Recovery: Python syntax errors
        for fname, content in list(state.files.items()):
            if fname.endswith(".py"):
                try:
                    compile(content, fname, "exec")
                except SyntaxError as syn_err:
                    state.add_activity(f"Recovery: Debugger Agent fixing syntax error in {fname}...", level="run")
                    fix_prompt = f"Fix syntax error in {fname}:\nError: {syn_err}\nCode:\n{content}"
                    try:
                        fixed = call_openrouter(
                            messages=[{"role": "user", "content": fix_prompt}],
                            system_prompt="You are an expert debugger. Return ONLY corrected code.",
                            temperature=0.1,
                            role="debugger",
                        )
                        cleaned_fixed = clean_code_block(fixed, "python")
                        self.workspace.write_file(fname, cleaned_fixed)
                        state.files[fname] = cleaned_fixed
                        state.add_activity(f"Recovery: Debugger Agent repaired syntax in {fname}", level="ok")
                    except Exception as debug_exc:
                        state.add_activity(f"Debugger repair failed for {fname}: {debug_exc}", level="bad")

        # 3. Contextual Recovery: Runtime crash, HTTP unresponsiveness, or missing frontend
        if state.runtime_status in ("FAILED", "DEGRADED") or state.failure_classification in ("HTTP_UNRESPONSIVE", "FRONTEND_NOT_RUNNING", "PROCESS_CRASHED"):
            state.add_activity("Recovery: Restarting and re-verifying runtime processes...", level="run")
            self.runner.restart(state)

    def execute_conversational_turn(
        self,
        state: ProjectState,
        message: str,
        selected_language: str = "Auto Detect",
    ) -> None:
        """Execute a conversational interaction turn with continuity and state persistence."""
        if state.is_awaiting_confirmation() or not state.can_execute_engineering():
            state.add_activity("Conversational execution blocked: confirmation barrier is active.", level="bad")
            return

        existing_files = self.workspace.list_files() if hasattr(self.workspace, "list_files") else []
        has_existing = bool(state.is_project_generated or state.files or existing_files)

        classification = TaskClassifier.classify(
            message=message,
            has_existing_project=has_existing,
            existing_files_count=len(existing_files),
        )
        state.current_classification = classification
        state.add_activity(f"Intent classified: [{classification}] '{message}'", level="run")

        # Save user message to persistent history and db
        turn_msg = {
            "role": "user",
            "content": message,
            "classification": classification,
            "timestamp": time.time(),
        }
        state.conversation_history.append(turn_msg)
        if state.db_manager and hasattr(state.db_manager, "messages"):
            try:
                state.db_manager.messages.save_message(
                    project_id=state.project_id,
                    role="user",
                    content=message,
                    classification=classification,
                    build_id=state.build_id,
                )
            except Exception:
                pass

        if classification == TaskClassification.NEW_PROJECT:
            # Fresh build: allocate distinct project identity and isolated workspace
            ts = int(time.time())
            new_pid = f"proj_{ts}_{uuid.uuid4().hex[:4]}"
            new_bid = f"bld_{ts}_{uuid.uuid4().hex[:6]}"
            new_cid = f"conv_{new_pid}_{uuid.uuid4().hex[:4]}"

            project_ws = WorkspaceManager.for_project(new_pid)
            self.workspace = project_ws
            if self.runner:
                self.runner.workspace = project_ws

            state.reset(new_goal=message, language=selected_language, project_id=new_pid, build_id=new_bid)
            state.conversation_id = new_cid
            state.build_start_time = time.time()
            state.is_running = True

            state.add_activity(f"Starting fresh isolated project ({new_pid}) for: '{message}'", level="run")

            if state.db_manager:
                try:
                    state.db_manager.sync_project_and_build_start(
                        project_id=new_pid,
                        project_name=getattr(state, "project_name", "SPIDY Project") or "SPIDY Project",
                        build_id=new_bid,
                        requirement=message,
                        detected_stack=selected_language,
                        workspace_path=str(project_ws.root),
                        estimated_duration=state.estimated_duration_str,
                    )
                    state.db_manager.messages.save_message(
                        project_id=new_pid,
                        role="user",
                        content=message,
                        classification=classification,
                        build_id=new_bid,
                    )
                except Exception:
                    pass

            self.analyze_and_plan(state)
            if state.user_approved:
                self.execute_build(state)

        elif classification in (
            TaskClassification.FEATURE_REQUEST,
            TaskClassification.MODIFICATION,
            TaskClassification.BUG_FIX,
            TaskClassification.REFACTOR,
        ):
            # Cleanly purge stale failed tasks so old errors never fail new delta turn
            state.tasks = [t for t in state.tasks if t.status in ("SUCCESS", "completed")]
            state.errors = []
            state.failure_reason = None
            state.known_issues = []
            state.reviewer_verdict = None

            # Incremental Plan Delta without wiping workspace
            state.add_activity(f"Generating Plan Delta for existing project ({len(existing_files)} files)...", level="run")
            state.current_phase = "PLAN"
            state.transition_to("PLANNING", f"Incremental update: {message}")

            existing_context = {}
            for fn in existing_files[:8]:
                if hasattr(self.workspace, "read_file"):
                    existing_context[fn] = self.workspace.read_file(fn)[:2000]

            delta_prompt = (
                f"Existing Project Goal: {state.goal}\n"
                f"Existing Architecture: {state.architecture_summary}\n"
                f"Existing Files: {list(existing_context.keys())}\n"
                f"User Request ({classification}): {message}\n\n"
                "Return a JSON object with keys:\n"
                "summary (str): what needs to be changed\n"
                "files_to_modify (list of str): existing files that need edits\n"
                "files_to_create (list of str): new files to add\n"
                "files_unaffected (list of str): files left untouched\n"
                "tasks (list of dicts with id, title, phase='BUILD', file_path)\n"
            )

            try:
                raw_delta = call_openrouter(
                    messages=[{"role": "user", "content": delta_prompt}],
                    system_prompt="You are a principal software engineer producing a precise Plan Delta. Output ONLY raw JSON.",
                    temperature=0.2,
                    role="planner",
                )
                delta_data = parse_json_response(raw_delta)
            except Exception:
                delta_data = {
                    "summary": f"Apply {message}",
                    "files_to_modify": existing_files[:2],
                    "files_to_create": [],
                    "files_unaffected": [f for f in existing_files if f not in existing_files[:2]],
                    "tasks": [{"id": "t-delta-1", "title": f"Update files for {message}", "phase": "BUILD", "file_path": existing_files[0] if existing_files else "app.py"}]
                }

            files_to_change = delta_data.get("files_to_modify", []) + delta_data.get("files_to_create", [])
            state.files_affected = files_to_change
            state.add_activity(f"Plan Delta established: modifying/creating {len(files_to_change)} files", level="ok")

            for dt in delta_data.get("tasks", []):
                state.add_task(
                    task_id=dt.get("id") or f"t-delta-{len(state.tasks)+1}",
                    title=dt.get("title", f"Apply changes to {dt.get('file_path')}"),
                    phase="BUILD",
                    agent="Developer Agent",
                    file_path=dt.get("file_path"),
                    is_required=True,
                    build_id=state.build_id,
                    project_id=state.project_id,
                )

            state.current_phase = "BUILD"
            state.transition_to("GENERATING", "Applying incremental modifications...")
            for fpath in files_to_change:
                current_code = self.workspace.read_file(fpath) if hasattr(self.workspace, "file_exists") and self.workspace.file_exists(fpath) else ""
                coder_prompt = (
                    f"User Request: {message}\n"
                    f"Delta Summary: {delta_data.get('summary')}\n"
                    f"File to generate/update: {fpath}\n"
                    f"Current File Content:\n{current_code}\n\n"
                    f"Output the complete, updated file content formatted with ### FILE: {fpath} header."
                )
                try:
                    raw_mod = call_openrouter(
                        messages=[{"role": "user", "content": coder_prompt}],
                        system_prompt="You are a senior engineer making precise, high quality updates. Output complete file.",
                        temperature=0.2,
                        role="coder",
                    )
                    parsed_mod = parse_multi_file_response(raw_mod)
                    if parsed_mod:
                        for p, content in parsed_mod.items():
                            target_p = p if p == fpath else fpath
                            self.workspace.write_file(target_p, content)
                            state.files[target_p] = content
                            state.add_activity(f"File updated: {target_p}", level="ok")
                    elif raw_mod.strip():
                        clean_content = clean_code_block(raw_mod)
                        self.workspace.write_file(fpath, clean_content)
                        state.files[fpath] = clean_content
                        state.add_activity(f"File updated: {fpath}", level="ok")
                except Exception as exc:
                    state.add_activity(f"Error updating {fpath}: {exc}", level="bad")

            for t in state.tasks:
                if t.phase == "BUILD" and t.status in ("QUEUED", "RUNNING"):
                    st_path = t.file_path
                    if st_path in state.files or not st_path:
                        state.complete_task(t.id)

            state.current_phase = "RUN"
            state.transition_to("RUNNING", "Restarting application server to reflect updates...")
            self.runner.restart(state)

            ws_dir = self._get_workspace_dir()
            verdict = self.reviewer_agent.review(state, ws_dir)

            has_failed_required = state.has_failed_required_tasks()
            is_verified = (
                state.is_project_generated
                and state.project_success
                and state.runtime_status == "RUNNING"
                and (not state.is_web_project or state.is_app_verified)
                and not has_failed_required
                and verdict.verdict == "PASS"
            )

            if is_verified:
                state.current_phase = "COMPLETE"
                state.transition_to("SUCCESS", "Iterative modification verified successfully.")
                state.add_activity("Conversational modification verified and live!", level="ok")
            else:
                state.current_phase = "FAILED"
                state.transition_to("FAILED", "Verification failed after update.")
                state.add_activity("Conversational update failed verification.", level="bad")

        elif classification == TaskClassification.VERIFICATION_REQUEST:
            state.add_activity("Re-running verification gates...", level="run")
            ws_dir = self._get_workspace_dir()
            verdict = self.reviewer_agent.review(state, ws_dir)
            self.runner.verify_existing(state)

        elif classification == TaskClassification.RUN_COMMAND:
            state.add_activity("Executing runtime process command...", level="run")
            self.runner.restart(state)

        elif classification == TaskClassification.EXPLANATION:
            state.add_activity("Generating architectural explanation...", level="run")
            explain_prompt = (
                f"Explain the architecture and functionality of the current project ({state.project_name}).\n"
                f"Files: {existing_files}\n"
                f"User Question: {message}"
            )
            try:
                explanation = call_openrouter(
                    messages=[{"role": "user", "content": explain_prompt}],
                    system_prompt="You are a senior tech lead explaining code to a developer. Be concise, technical, and clear.",
                    temperature=0.3,
                    role="general",
                )
                state.add_activity(explanation[:300] + "...", level="ok")
            except Exception as exc:
                state.add_activity(f"Explanation failed: {exc}", level="bad")

        summary_msg = f"Completed action for [{classification}]: {message}"
        assistant_record = {
            "role": "assistant",
            "content": summary_msg,
            "classification": classification,
            "timestamp": time.time(),
        }
        state.conversation_history.append(assistant_record)
        if state.db_manager and hasattr(state.db_manager, "messages"):
            try:
                state.db_manager.messages.save_message(
                    project_id=state.project_id,
                    role="assistant",
                    content=summary_msg,
                    classification=classification,
                    build_id=state.build_id,
                )
            except Exception:
                pass

    def run_iterative_update(self, state: ProjectState, instruction: str) -> None:
        """Handle follow-up prompt ('Add 3D lighting', 'Add auth') on existing workspace."""
        self.execute_conversational_turn(state, instruction)
