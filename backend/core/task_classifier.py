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

        # 1. Explicit fresh project patterns (e.g. "start from scratch", "brand new project")
        new_project_explicit = (
            r"\b(start from scratch|brand new project|create a new project|fresh project|new project|new app|new application)\b"
        )
        if re.search(new_project_explicit, text):
            return TaskClassification.NEW_PROJECT

        # 0. Affirmative confirmation responses
        affirmative_patterns = (
            r"^(yes|yep|yeah|confirm|confirmed|proceed|go ahead|looks good|ok|sure|build it|do it)\b|"
            r"^(start|start now|start implementation|start building)$|"
            r"that'?s\s+(what\s+i\s+want|correct|right)|"
            r"yes,\s*that'?s\s+what\s+i\s+want"
        )
        if re.search(affirmative_patterns, text):
            return TaskClassification.NEW_PROJECT if (not has_existing_project and existing_files_count == 0) else TaskClassification.MODIFICATION

        # Check for explicit contextual continuation phrases targeting an existing project
        continuation_phrases = (
            r"\b(to the current|to this|in the current|into the current|inside the existing|in my existing|to my existing|add to this|add to the current)\b"
        )
        has_continuation = bool(re.search(continuation_phrases, text))

        # Check for contextual pronouns referring to existing app ("make it...", "turn it into...", "style it...")
        is_contextual_pronoun_mod = bool(
            re.search(r"^(make|turn|change|convert|style|tweak|update|theme)\s+it\b", text)
            or re.search(r"\b(make it|turn it|convert it|change it|update it|theme it)\b", text)
            or re.search(r"\b(in this app|to this app|in the current|to the current|my existing)\b", text)
        )

        # Standalone application creation pattern (e.g. "build an interactive 3D portfolio website", "create a 3D website about Messi", "make an expense tracker")
        app_noun_pattern = (
            r"\b(website|web\s*app|webpage|page|portfolio|dashboard|tracker|game|tool|service|api|backend|frontend|"
            r"full-stack|fullstack|microservice|app|application|system|project|platform|utility|interface|client|bot|store|shop|blog|viewer|explorer)\b"
        )
        creation_verb_pattern = r"^(build|create|develop|generate|make|write|implement|launch|deploy|start)\b"

        if (
            re.search(creation_verb_pattern, text)
            and re.search(app_noun_pattern, text)
            and not has_continuation
            and not is_contextual_pronoun_mod
        ):
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

        # Contextual pronoun modifications (e.g. "make it about Messi", "make it more interactive", "turn it into...")
        if has_existing_project and re.search(r"\b(make it|turn it|convert it|change it|update it|theme it)\b", text):
            return TaskClassification.MODIFICATION

        # 11. Feature requests (adding new things to existing system)
        if re.search(r"\b(add|include|integrate|support|attach|also add|new feature)\b", text):
            return TaskClassification.FEATURE_REQUEST

        # 12. Contextual modifications vs new project verbs
        if has_existing_project:
            if re.search(r"^(make|turn|change|convert|style|tweak)\s+it\b", text):
                return TaskClassification.MODIFICATION
            if re.search(r"^(add|include|insert|attach|give it)\b", text):
                return TaskClassification.FEATURE_REQUEST

        # If starts with build/write/create and describes an independent target
        if re.search(r"^(build|create|write|develop|make)\b", text):
            # If explicit contextual pronoun used with existing project
            if has_existing_project and re.search(r"\b(it|this|current|existing)\b", text):
                return TaskClassification.MODIFICATION
            return TaskClassification.NEW_PROJECT

        # 13. Default based on context
        if has_existing_project or existing_files_count > 0:
            if "change" in text or "replace" in text or "tweak" in text or "make it" in text:
                return TaskClassification.MODIFICATION
            return TaskClassification.FEATURE_REQUEST

        return TaskClassification.NEW_PROJECT
