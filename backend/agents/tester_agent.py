"""Tester Agent for NOVA Code Lab.

Verifies process execution, performs health checks, and validates runtime behavior.
"""

from backend.core.base_agent import BaseAgent


class TesterAgent(BaseAgent):
    """Executes process launch and health check verification."""

    def __init__(self):
        super().__init__(name="Tester & Runner Agent", role="Process Testing & Health Check", default_llm_role="fast")
