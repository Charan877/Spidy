"""Task Classifier for SPIDY.

Classifies incoming user messages into granular engineering intents
to determine appropriate autonomous workflow paths (e.g. Plan Delta vs Fresh Build).
Strictly prevents stale project context reuse when a user requests a new project.
"""

import re
from typing import Optional, List, Dict, Any


class TaskClassification:
    NEW_PROJECT = "NEW_PROJECT"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    MODIFICATION = "MODIFICATION"
    BUG_FIX = "BUG_FIX"
    DEBUG_REQUEST = "DEBUG_REQUEST"
    REFACTOR = "REFACTOR"
    EXPLANATION = "EXPLANATION"
    VERIFICATION_REQUEST = "VERIFICATION_REQUEST"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENTATION = "DOCUMENTATION"
    RUN_COMMAND = "RUN_COMMAND"


class TaskClassifier:
    """Classifies user requests using deterministic intent patterns."""

    @classmethod
    def classify(
        cls,
        message: str,
        has_existing_project: bool = False,
        existing_files_count: int = 0,
    ) -> str:
        text = (message or "").strip().lower()

        # 1. Explicit or implicit NEW PROJECT patterns
        # Matches commands creating an app, website, service, tool, or program
        new_project_explicit = (
            r"\b(start from scratch|brand new project|create a new project|fresh project|new project|new app|new application)\b"
        )
        if re.search(new_project_explicit, text):
            return TaskClassification.NEW_PROJECT

        new_project_phrase = (
            r"\b(build|create|develop|generate|make|write|implement)\s+(a|an|the|me a|me an)?\s*(new\s+)?"
            r"(full-stack|fullstack|web|rest|fastapi|flask|react|frontend|backend|cli|python|javascript|typescript|"
            r"portfolio|dashboard|taskflow|task-flow|todo|microservice|app|application|service|tool|game|program|website|system|project)\b"
        )
        if re.search(new_project_phrase, text):
            # Check if user explicitly specifies modifying current project instead
            continuation_phrases = r"\b(to the current|to this|in the current|into the current|also add|add to|inside the existing)\b"
            if not re.search(continuation_phrases, text):
                return TaskClassification.NEW_PROJECT

        # If starts with project building verb and has no existing project
        if not has_existing_project and existing_files_count == 0:
            return TaskClassification.NEW_PROJECT

        # 2. Explanation / Query
        if re.search(r"^(how does|what is|explain|walk me through|show me how|why does)\b", text):
            return TaskClassification.EXPLANATION

        # 3. Verification / Testing
        if re.search(r"\b(verify|run tests|run test|test this|re-verify|check health|check if it works)\b", text):
            return TaskClassification.VERIFICATION_REQUEST

        # 4. Debugging
        if re.search(r"\b(debug|inspect log|view logs|trace error|find why)\b", text):
            return TaskClassification.DEBUG_REQUEST

        # 5. Bug Fix
        if re.search(r"\b(fix|broken|not working|doesn't work|does not work|failed|error|crash|button.*not respond|bug|typo)\b", text):
            return TaskClassification.BUG_FIX

        # 6. Run / Process commands
        if re.search(r"\b(restart server|stop server|start server|kill process|restart app)\b", text):
            return TaskClassification.RUN_COMMAND

        # 7. Refactoring / Optimization
        if re.search(r"\b(refactor|restructure|clean up|optimize|tidy up)\b", text):
            return TaskClassification.REFACTOR

        # 8. Documentation
        if re.search(r"\b(document|add docs|write readme|update readme|documentation)\b", text):
            return TaskClassification.DOCUMENTATION

        # 9. Configuration
        if re.search(r"\b(configure|change port|env variable|settings|config)\b", text):
            return TaskClassification.CONFIGURATION

        # 10. Modifications (styling, text changes, alterations to existing components)
        if re.search(r"\b(change|update|modify|replace|alter|edit|rename|style|tweak|make the.*(smaller|larger|darker|lighter|blue|red))\b", text):
            return TaskClassification.MODIFICATION

        # 11. Feature requests (adding new things to existing system)
        if re.search(r"\b(add|include|integrate|support|attach|also add|new feature)\b", text):
            return TaskClassification.FEATURE_REQUEST

        # 12. If starts with build/write/create and describes an independent target
        if re.search(r"^(build|create|write|develop|make)\b", text):
            return TaskClassification.NEW_PROJECT

        # 13. Default based on context
        if has_existing_project or existing_files_count > 0:
            if "change" in text or "replace" in text or "tweak" in text:
                return TaskClassification.MODIFICATION
            return TaskClassification.FEATURE_REQUEST

        return TaskClassification.NEW_PROJECT
