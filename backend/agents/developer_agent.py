"""Developer Agent for NOVA Code Lab.

Generates production-ready multi-file source code. Wraps generator_agent.py.
"""

from backend.core.base_agent import BaseAgent
from backend.agents.generator_impl import generate_code


class DeveloperAgent(BaseAgent):
    """Writes multi-file source code for software projects."""

    def __init__(self):
        super().__init__(name="Developer Agent", role="Code Generation & Construction", default_llm_role="coder")

    def generate(self, requirement: str, language: str = "Python") -> str:
        return generate_code(requirement, language=language)
