"""Semantic Requirement Understanding Layer for SPIDY.

Converts natural-language software requests into structured internal engineering specifications
before planning begins. Infers implementation details that do not require user input,
captures domain, audience, capabilities, experience expectations, engineering defaults,
and verification requirements, and formulates a concise interpretation for user confirmation.
"""

from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("spidy.semantic_requirement")


class VerificationRequirements(list):
    """List of verification requirement strings supporting dict-like inspection."""
    def get(self, key: str, default: Any = None) -> Any:
        key_lower = key.lower()
        if "webgl" in key_lower:
            has_webgl = any("webgl" in str(x).lower() for x in self)
            return has_webgl if has_webgl else default
        if "canvas" in key_lower:
            has_canvas = any("canvas" in str(x).lower() or "webgl" in str(x).lower() for x in self)
            return has_canvas if has_canvas else default
        if "api" in key_lower:
            has_api = any("api" in str(x).lower() or "endpoint" in str(x).lower() for x in self)
            return has_api if has_api else default
        for item in self:
            if key_lower in str(item).lower():
                return True
        return default


@dataclass
class EngineeringSpecification:
    """Structured internal engineering specification inferred from user request."""
    user_intent: str
    domain: str
    audience: Optional[str] = None
    application_type: str = "web"  # "web_3d", "web", "api", "fullstack", "cli", "library"
    core_capabilities: List[str] = field(default_factory=list)
    content_requirements: List[str] = field(default_factory=list)
    experience_expectations: List[str] = field(default_factory=list)
    explicit_constraints: List[str] = field(default_factory=list)
    engineering_defaults: Dict[str, Any] = field(default_factory=dict)
    verification_requirements: Any = field(default_factory=VerificationRequirements)
    concise_interpretation: str = ""
    is_modification: bool = False
    intent_classification: str = "NEW_PROJECT"  # "NEW_PROJECT" or "MODIFICATION"
    target_project_id: Optional[str] = None
    diff_summary: Optional[str] = None
    clarification_questions: List[str] = field(default_factory=list)
    status: str = "PENDING_CONFIRMATION"  # "PENDING_CONFIRMATION", "CONFIRMED", "REJECTED"

    def __post_init__(self):
        if not isinstance(self.verification_requirements, VerificationRequirements):
            self.verification_requirements = VerificationRequirements(self.verification_requirements or [])
        if self.is_modification and self.intent_classification != "MODIFICATION":
            self.intent_classification = "MODIFICATION"
        elif self.intent_classification == "MODIFICATION":
            self.is_modification = True
        if not isinstance(self.engineering_defaults, dict):
            self.engineering_defaults = {}
        if "tech_stack" not in self.engineering_defaults:
            stack = []
            fe = self.engineering_defaults.get("frontend")
            if fe:
                stack.extend([s.strip() for s in fe.replace("/", ",").split(",") if s.strip()])
            be = self.engineering_defaults.get("backend")
            if be and be.lower() != "none":
                stack.extend([s.strip() for s in be.replace("/", ",").split(",") if s.strip()])
            if not stack:
                if self.application_type == "web_3d":
                    stack = ["HTML5", "Three.js", "WebGL", "CSS3"]
                elif self.application_type == "api":
                    stack = ["Python", "FastAPI", "SQLite"]
                else:
                    stack = ["HTML5", "JavaScript", "CSS3"]
            self.engineering_defaults["tech_stack"] = stack

    @property
    def interpretation(self) -> str:
        return self.concise_interpretation

    @interpretation.setter
    def interpretation(self, val: str) -> None:
        self.concise_interpretation = val

    @property
    def is_confirmed(self) -> bool:
        return self.status == "CONFIRMED"

    @property
    def user_confirmed(self) -> bool:
        return self.status == "CONFIRMED"

    @user_confirmed.setter
    def user_confirmed(self, val: bool) -> None:
        self.status = "CONFIRMED" if val else "PENDING_CONFIRMATION"

    @property
    def interpretation_status(self) -> str:
        return "CONFIRMED" if self.status == "CONFIRMED" else "PENDING"

    @interpretation_status.setter
    def interpretation_status(self, val: str) -> None:
        if str(val).upper() in ("CONFIRMED", "TRUE"):
            self.status = "CONFIRMED"
        else:
            self.status = "PENDING_CONFIRMATION"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_intent": self.user_intent,
            "domain": self.domain,
            "audience": self.audience,
            "application_type": self.application_type,
            "core_capabilities": list(self.core_capabilities),
            "content_requirements": list(self.content_requirements),
            "experience_expectations": list(self.experience_expectations),
            "explicit_constraints": list(self.explicit_constraints),
            "engineering_defaults": dict(self.engineering_defaults),
            "verification_requirements": list(self.verification_requirements),
            "concise_interpretation": self.concise_interpretation,
            "is_modification": self.is_modification,
            "intent_classification": self.intent_classification,
            "target_project_id": self.target_project_id,
            "diff_summary": self.diff_summary,
            "clarification_questions": list(self.clarification_questions),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EngineeringSpecification":
        is_mod = data.get("is_modification", False)
        intent = data.get("intent_classification", "MODIFICATION" if is_mod else "NEW_PROJECT")
        return cls(
            user_intent=data.get("user_intent", ""),
            domain=data.get("domain", "General"),
            audience=data.get("audience"),
            application_type=data.get("application_type", "web"),
            core_capabilities=data.get("core_capabilities", []),
            content_requirements=data.get("content_requirements", []),
            experience_expectations=data.get("experience_expectations", []),
            explicit_constraints=data.get("explicit_constraints", []),
            engineering_defaults=data.get("engineering_defaults", {}),
            verification_requirements=data.get("verification_requirements", []),
            concise_interpretation=data.get("concise_interpretation", ""),
            is_modification=is_mod or (intent == "MODIFICATION"),
            intent_classification=intent,
            target_project_id=data.get("target_project_id"),
            diff_summary=data.get("diff_summary"),
            clarification_questions=data.get("clarification_questions", []),
            status=data.get("status", "PENDING_CONFIRMATION"),
        )


class SemanticRequirementAnalyzer:
    """Analyzes natural-language requests into structured engineering specifications."""

    @classmethod
    def analyze(
        cls,
        requirement: str,
        active_context: Optional[Any] = None,
        existing_project_spec: Optional[Dict[str, Any]] = None,
        selected_language: str = "Auto Detect",
        context: Optional[Any] = None,
    ) -> EngineeringSpecification:
        """Convert a user's natural language request into an EngineeringSpecification."""
        if context is not None and active_context is None:
            active_context = context

        req_clean = (requirement or "").strip()
        req_lower = req_clean.lower()

        # Check if there is an active existing project that actually has files or a prior spec
        ctx_pid = None
        has_existing_files = False
        if active_context:
            if isinstance(active_context, dict):
                ctx_pid = active_context.get("project_id") or active_context.get("target_project_id")
                if not existing_project_spec and "application_type" in active_context:
                    existing_project_spec = active_context
            else:
                ctx_pid = getattr(active_context, "project_id", None)

        if ctx_pid and ctx_pid != "spidy-default":
            try:
                from backend.core.workspace_manager import WorkspaceManager
                ws = WorkspaceManager.for_project(ctx_pid)
                if ws and hasattr(ws, "list_files"):
                    has_existing_files = len(ws.list_files()) > 0
            except Exception:
                has_existing_files = False

        has_active_project = bool(
            has_existing_files or (existing_project_spec and len(existing_project_spec) > 0)
        )
        is_modification = False
        target_pid = None
        diff_summary = None

        # Standalone application creation patterns (e.g. "Build an interactive 3D portfolio website", "Create a 3D website about Messi", "Make an expense tracker")
        app_noun_pattern = (
            r"\b(website|web\s*app|webpage|page|portfolio|dashboard|tracker|game|tool|service|api|backend|frontend|"
            r"full-stack|fullstack|microservice|app|application|system|project|platform|utility|interface|client|bot|store|shop|blog|viewer|explorer)\b"
        )
        creation_verb_pattern = r"^(build|create|develop|generate|make|write|implement|launch|deploy|start)\b"

        continuation_phrases = (
            r"\b(to the current|to this|in the current|into the current|inside the existing|in my existing|to my existing|add to this|add to the current)\b"
        )
        is_explicit_continuation = bool(re.search(continuation_phrases, req_lower))

        is_contextual_pronoun = bool(
            re.search(r"^(make|turn|change|convert|style|tweak|update|theme)\s+it\b", req_lower)
            or re.search(r"\b(make it|turn it|convert it|change it|update it|theme it)\b", req_lower)
            or re.search(r"\b(in this app|to this app|in the current|to the current|my existing)\b", req_lower)
        )

        is_standalone_new = (
            bool(re.search(r"\b(brand new project|start from scratch|fresh project|new project|new app)\b", req_lower))
            or (
                bool(re.search(creation_verb_pattern, req_lower))
                and bool(re.search(app_noun_pattern, req_lower))
                and not is_explicit_continuation
                and not is_contextual_pronoun
            )
        )

        if has_active_project and not is_standalone_new:
            # Contextual signals: pronouns ('it', 'this', 'current', 'existing'), modification verbs ('add', 'make it', 'turn it', 'change', 'update', 'modify', 'replace', 'fix')
            is_contextual = bool(
                is_contextual_pronoun
                or is_explicit_continuation
                or re.search(r"\b(it|this|current|existing|my app|our app|the app|the website|the project)\b", req_lower)
                or re.search(r"^(make|turn|change|convert|style|tweak|add|include|insert|modify|update|replace|remove|fix)\b", req_lower)
            )
            # If not an explicit fresh build command
            if is_contextual and not re.search(r"\b(brand new project|start from scratch|fresh project)\b", req_lower):
                is_modification = True
                target_pid = ctx_pid

        # Attempt LLM-driven semantic understanding first if router is available
        spec = cls._try_llm_analysis(req_clean, has_active_project, existing_project_spec, selected_language)
        if spec:
            spec.is_modification = is_modification
            spec.intent_classification = "MODIFICATION" if is_modification else "NEW_PROJECT"
            spec.target_project_id = target_pid if is_modification else None
            return spec

        # Fallback: Deterministic semantic inference engine
        return cls._heuristic_analysis(req_clean, is_modification, target_pid, existing_project_spec, selected_language)

    @classmethod
    def _try_llm_analysis(
        cls,
        requirement: str,
        has_active_project: bool,
        existing_project_spec: Optional[Dict[str, Any]],
        selected_language: str,
    ) -> Optional[EngineeringSpecification]:
        """Use ModelRouter LLM for deep semantic requirement reasoning."""
        # Authoritative ModelRouter import - will raise immediately if module is missing
        from backend.core.llm.model_router import get_model_router
        from backend.core.openrouter_client import call_openrouter, parse_json_response

        router = get_model_router()
        if not router.is_configured():
            logger.info("AI provider credentials not configured in ModelRouter; falling back to deterministic heuristic analysis.")
            return None

        try:
            system_prompt = (
                "You are an expert AI Software Architect and Requirements Engineer for SPIDY.\n"
                "Your job is to understand natural language software requests and infer a complete, practical engineering specification.\n"
                "Infer implementation details that do not require user input (frameworks, folder structures, libraries, ports).\n"
                "Only specify clarification_questions if a critical product requirement genuinely cannot be determined.\n"
                "Respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                '  "user_intent": "Summary of primary user goal",\n'
                '  "domain": "Domain/industry (e.g. Sports, Personal Finance, Developer Tools)",\n'
                '  "audience": "Target audience if inferable",\n'
                '  "application_type": "web_3d | web | api | fullstack | cli",\n'
                '  "core_capabilities": ["Feature 1", "Feature 2", ...],\n'
                '  "content_requirements": ["Content item 1", "Content item 2", ...],\n'
                '  "experience_expectations": ["UX expectation 1", ...],\n'
                '  "explicit_constraints": ["User constraints if any, or empty"],\n'
                '  "engineering_defaults": {\n'
                '      "frontend": "e.g. Three.js / HTML5 or React",\n'
                '      "tech_stack": ["HTML5", "Three.js", "WebGL", "CSS3"],\n'
                '      "backend": "e.g. FastAPI or None",\n'
                '      "styling": "e.g. Dark cinematic or Modern clean",\n'
                '      "storage": "e.g. SQLite or None"\n'
                '  },\n'
                '  "verification_requirements": ["Specific verification checks needed (e.g. WebGL canvas rendering, DOM structure, API routes)"],\n'
                '  "concise_interpretation": "A 2-3 sentence clear, professional interpretation of what you understand the user wants to build and will produce."\n'
                "}"
            )

            context_msg = f"User Request: {requirement}\nSelected Language: {selected_language}\n"
            if has_active_project and existing_project_spec:
                context_msg += f"Active Existing Project Context: {json.dumps(existing_project_spec)}\n"

            raw_resp = call_openrouter(
                messages=[{"role": "user", "content": context_msg}],
                system_prompt=system_prompt,
                temperature=0.2,
                role="planner",
            )
            parsed = parse_json_response(raw_resp)
            if parsed and isinstance(parsed, dict) and "user_intent" in parsed:
                return EngineeringSpecification.from_dict(parsed)
            else:
                logger.warning(
                    f"LLM semantic requirement analysis returned unparseable or incomplete response: {str(raw_resp)[:200]}. "
                    "Falling back to deterministic heuristic analysis."
                )
        except Exception as exc:
            logger.warning(
                f"LLM provider runtime failure during semantic requirement analysis: {exc}. "
                "Falling back to deterministic heuristic analysis.",
                exc_info=True,
            )
        return None

    @classmethod
    def _heuristic_analysis(
        cls,
        requirement: str,
        is_modification: bool,
        target_pid: Optional[str],
        existing_project_spec: Optional[Dict[str, Any]],
        selected_language: str,
    ) -> EngineeringSpecification:
        """Deterministic semantic inference engine for offline or fallback execution."""
        req_lower = requirement.lower()

        # 1. Detect Application Type
        if is_modification and existing_project_spec and existing_project_spec.get("application_type"):
            app_type = existing_project_spec["application_type"]
        else:
            is_3d = bool(
                re.search(r"\b(3d|threejs|three\.js|webgl|canvas|solar system|orbit|planet|astronomy|scene|camera)\b", req_lower)
            )
            is_api = bool(
                re.search(r"\b(api|rest api|fastapi|flask|endpoint|backend service|microservice)\b", req_lower)
                and not re.search(r"\b(frontend|dashboard|ui|website|web app)\b", req_lower)
            )
            is_fullstack = bool(
                re.search(r"\b(full-stack|fullstack)\b", req_lower)
                or selected_language == "Fullstack"
                or (
                    re.search(r"\b(fastapi|flask|backend|api)\b", req_lower)
                    and re.search(r"\b(frontend|dashboard|ui|website|html)\b", req_lower)
                )
            )
            is_cli = bool(re.search(r"\b(cli|command line|terminal app|script)\b", req_lower))

            if is_3d:
                app_type = "web_3d"
            elif is_api:
                app_type = "api"
            elif is_fullstack:
                app_type = "fullstack"
            elif is_cli:
                app_type = "cli"
            else:
                app_type = "web"

        # 2. Extract Domain & Topic
        domain = "General Software"
        audience = "General Users"
        topic = "Application"

        if re.search(r"\b(messi|football|soccer|club|roster|fifa|league|ballon d'or)\b", req_lower):
            domain = "Sports & Athletics"
            audience = "Football fans, sports enthusiasts, and general public"
            topic = "Lionel Messi Career & Milestones" if "messi" in req_lower else "Football Club Portal"
        elif re.search(r"\b(expense|budget|finance|money|spend|wallet|tracker)\b", req_lower):
            domain = "Personal Finance"
            audience = "Individuals tracking daily expenses and financial budgets"
            topic = "Expense and Budget Management"
        elif re.search(r"\b(portfolio|resume|cv|personal website|showcase)\b", req_lower):
            domain = "Professional Portfolio"
            audience = "Recruiters, engineering peers, and clients"
            topic = "Interactive Developer Portfolio"
        elif re.search(r"\b(books?|librar(?:y|ies)|catalogs?|readings?|authors?)\b", req_lower):
            domain = "Literature & Education"
            audience = "Book readers, librarians, and catalog managers"
            topic = "Book Catalog & Reading Management"
        elif re.search(r"\b(solar system|space|planet|orbit|galaxy|astronomy)\b", req_lower):
            domain = "Science & Space Exploration"
            audience = "Students, educators, and astronomy enthusiasts"
            topic = "Solar System Simulation"
        elif re.search(r"\b(recipe|dish|cooking|culinary|food)\b", req_lower):
            domain = "Culinary & Lifestyle"
            audience = "Home cooks and food enthusiasts"
            topic = "Recipe Discovery and Sharing"
        elif re.search(r"\b(sensor|telemetry|iot|hardware|monitoring)\b", req_lower):
            domain = "IoT & Hardware Telemetry"
            audience = "System operators and IoT telemetry engineers"
            topic = "IoT Sensor Telemetry Service"

        # 3. Derive Core Capabilities & Content
        capabilities: List[str] = []
        content_reqs: List[str] = []
        experience_expectations: List[str] = []
        verification_reqs: List[str] = []
        engineering_defaults: Dict[str, Any] = {}

        if app_type == "web_3d":
            capabilities = [
                "Interactive 3D WebGL scene with procedural models and lighting",
                "Orbit / camera controls for user perspective manipulation",
                "Responsive HUD telemetry overlay with domain content",
                "Smooth 60fps render animation loop with responsive resize handling",
            ]
            content_reqs = [
                f"Detailed thematic assets and data for {topic}",
                "Structured milestone timeline or statistic counters",
                "Visual navigation controls and informational cards",
            ]
            experience_expectations = [
                "Immersive visual experience with clean dark/atmospheric theme",
                "Immediate interactive feedback without frame drops",
                "No visual artifacts, blank screens, or WebGL context crashes",
            ]
            verification_reqs = [
                "WebGL rendering surface initialized with non-zero dimensions",
                "Valid WebGL context (webgl or webgl2) with zero GL errors",
                "Active requestAnimationFrame render loop",
                "DOM HUD structure present and populated with non-empty content",
                "Zero uncaught JavaScript exceptions or console errors",
            ]
            engineering_defaults = {
                "frontend": "Three.js / WebGL with vanilla JavaScript and CSS",
                "tech_stack": ["HTML5", "Three.js", "WebGL", "CSS3"],
                "backend": "None",
                "styling": "Dark immersive theme with glassmorphism HUD",
                "storage": "Client-side state",
                "port_strategy": "Dynamic HTTP server",
            }

        elif app_type == "api":
            capabilities = [
                "RESTful JSON API with structured CRUD endpoints",
                "Automated request validation and standardized error schemas",
                "FastAPI / OpenAPI interactive documentation (/docs)",
                "System health check readiness endpoint (/health)",
            ]
            content_reqs = [
                f"Data models and schemas for {topic}",
                "Persistent SQLite database storage with auto-initialization",
                "Representative seed records for immediate testing",
            ]
            experience_expectations = [
                "Fast sub-50ms JSON responses with correct HTTP status codes",
                "Clean OpenAPI schema documentation",
            ]
            verification_reqs = [
                "HTTP 200 response on root and /health endpoints",
                "OpenAPI /docs endpoint accessible and valid",
                "Successful GET and POST CRUD transactions against primary API resource",
                "Valid JSON response format matching schema",
            ]
            engineering_defaults = {
                "frontend": "None",
                "backend": "FastAPI (Python) with Uvicorn ASGI",
                "tech_stack": ["Python", "FastAPI", "Uvicorn", "SQLite"],
                "styling": "None",
                "storage": "SQLite database",
                "port_strategy": "Dynamic port with auto-binding",
            }

        elif app_type == "fullstack":
            capabilities = [
                "Interactive frontend UI with real-time backend API synchronization",
                "Complete CRUD record management (create, read, update, delete)",
                "Asynchronous data fetching with loading states and error handling",
                "Persistent database storage",
            ]
            content_reqs = [
                f"Domain data records and forms for {topic}",
                "Structured dashboard / list view with item filtering",
                "Real-time feedback on user submissions",
            ]
            experience_expectations = [
                "Seamless client-server integration without CORS errors",
                "Intuitive form inputs with input validation",
            ]
            verification_reqs = [
                "Frontend loads cleanly without uncaught JS console errors",
                "Backend API service healthy and responsive",
                "Successful end-to-end CRUD roundtrip verified from frontend to backend",
                "Persistent database records verified",
            ]
            engineering_defaults = {
                "frontend": "HTML5 / Modern JavaScript with CSS layout",
                "backend": "FastAPI (Python)",
                "tech_stack": ["FastAPI", "HTML5", "JavaScript", "SQLite"],
                "styling": "Modern responsive dashboard UI",
                "storage": "SQLite database",
                "port_strategy": "Dual dynamic ports with CORS enabled",
            }

        else:  # Normal Web
            capabilities = [
                f"Interactive single-page application for {topic}",
                "Responsive layout optimized for modern browsers",
                "Dynamic interactive controls and content navigation",
            ]
            content_reqs = [
                f"Comprehensive content sections for {topic}",
                "Engaging visual presentation, typography, and iconography",
            ]
            experience_expectations = [
                "Fast page load with polished visual design",
                "Zero console errors or missing resource requests",
            ]
            verification_reqs = [
                "Page loads successfully with HTTP 200",
                "DOM structure contains root elements, headings, and interactive elements",
                "Zero uncaught JavaScript exceptions",
                "All referenced stylesheets and scripts resolved cleanly",
            ]
            engineering_defaults = {
                "frontend": "HTML5, CSS3, Modern JavaScript",
                "tech_stack": ["HTML5", "CSS3", "JavaScript"],
                "backend": "None",
                "styling": "Modern responsive CSS styling",
                "storage": "Local state",
                "port_strategy": "Dynamic HTTP server",
            }

        # Specific feature mentions in user prompt
        if "timeline" in req_lower and not any("timeline" in c.lower() for c in capabilities):
            capabilities.append("Interactive chronological career and achievement timeline")
        if "troph" in req_lower and not any("troph" in c.lower() for c in capabilities):
            capabilities.append("Trophy showcase and championship awards cabinet")
        if "ballon" in req_lower and not any("ballon" in c.lower() for c in capabilities):
            capabilities.append("Ballon d'Or honors and awards display")
        if "messi" in req_lower and not any("messi" in c.lower() for c in capabilities):
            capabilities.append("Lionel Messi career statistics and biography")

        # 4. Formulate Concise Interpretation for User Confirmation
        diff_summary = None
        if is_modification:
            concise_interpretation = (
                f"You want to update the existing application by tailoring it to '{topic}'. "
                f"I will implement the requested enhancements ({', '.join(capabilities[:2])}) "
                f"while maintaining the existing architecture and ensuring full browser verification."
            )
            diff_summary = f"Update content, styling, and interactivity for {topic}."
        else:
            concise_interpretation = (
                f"You want to build a {app_type.replace('_', ' ').upper()} application for '{topic}' in the {domain} domain. "
                f"I will engineer this using {engineering_defaults.get('frontend', 'Modern Web Technologies')} "
                f"with {', '.join(capabilities[:2]).lower()}, and verify it thoroughly in a real browser environment."
            )

        return EngineeringSpecification(
            user_intent=requirement,
            domain=domain,
            audience=audience,
            application_type=app_type,
            core_capabilities=capabilities,
            content_requirements=content_reqs,
            experience_expectations=experience_expectations,
            explicit_constraints=[],
            engineering_defaults=engineering_defaults,
            verification_requirements=verification_reqs,
            concise_interpretation=concise_interpretation,
            is_modification=is_modification,
            intent_classification="MODIFICATION" if is_modification else "NEW_PROJECT",
            target_project_id=target_pid,
            diff_summary=diff_summary,
            status="PENDING_CONFIRMATION",
        )

    @classmethod
    def update_with_feedback(
        cls,
        spec: EngineeringSpecification,
        feedback: str,
        is_rejection: bool = False,
    ) -> EngineeringSpecification:
        """Update an existing specification based on user rejection or clarifying feedback."""
        fb_clean = (feedback or "").strip()
        fb_lower = fb_clean.lower()

        # Update intent and capabilities based on feedback
        spec.explicit_constraints.append(f"User Feedback: {fb_clean}")
        spec.content_requirements.append(f"User requested: {fb_clean}")
        spec.core_capabilities.append(f"Incorporate user feedback: {fb_clean}")
        if is_rejection:
            spec.status = "REJECTED"
        else:
            spec.status = "PENDING_CONFIRMATION"

        # Check for scope or tech shifts in feedback
        if "3d" in fb_lower or "webgl" in fb_lower or "three" in fb_lower:
            spec.application_type = "web_3d"
            spec.engineering_defaults["frontend"] = "Three.js / WebGL"
            spec.engineering_defaults["tech_stack"] = ["HTML5", "Three.js", "WebGL", "CSS3"]
        elif "api" in fb_lower and "frontend" not in fb_lower:
            spec.application_type = "api"
            spec.engineering_defaults["backend"] = "FastAPI"
            spec.engineering_defaults["tech_stack"] = ["Python", "FastAPI", "Uvicorn", "SQLite"]
        elif "fullstack" in fb_lower or "backend" in fb_lower:
            spec.application_type = "fullstack"
            spec.engineering_defaults["tech_stack"] = ["FastAPI", "HTML5", "JavaScript", "SQLite"]

        # Update concise interpretation
        spec.concise_interpretation = (
            f"Revised Understanding: Based on your feedback ('{fb_clean}'), I have adjusted the plan for {spec.user_intent}. "
            f"I will proceed with an updated {spec.application_type.replace('_', ' ').upper()} architecture matching your exact specifications."
        )
        return spec
