"""Planner Agent for NOVA Code Lab.

Analyzes natural-language requirements, structures project goals, and generates task plans.
"""

from backend.core.base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    """Parses user requirements into actionable task breakdowns."""

    def __init__(self):
        super().__init__(name="Planner Agent", role="Task & Requirement Planning", default_llm_role="planner")
