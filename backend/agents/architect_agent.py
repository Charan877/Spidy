"""Architect Agent for NOVA Code Lab.

Designs software architecture, stack selection, and file directory structures.
"""

from backend.core.base_agent import BaseAgent


class ArchitectAgent(BaseAgent):
    """Defines system architecture, technology stack, and project structure."""

    def __init__(self):
        super().__init__(name="Architect Agent", role="Architecture & Technology Stack Design", default_llm_role="architect")
