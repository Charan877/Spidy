"""Debugger Agent.

This agent receives source code, checks it for errors (Python compile syntax check or multi-language format review),
and asks the LLM to fix syntax and logical problems.
"""

import os
import re
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "openrouter/free"
REQUEST_TIMEOUT = 45.0

SYSTEM_PROMPT = (
    "You are a careful software debugger. "
    "You receive code together with any detected errors. "
    "Fix syntax errors, wrong logic, and runtime problems. "
    "Return ONLY the corrected raw code inside Markdown code fences or clean text. "
    "Do NOT add explanations outside the code."
)


def _get_client() -> OpenAI:
    """Create and return an OpenAI-compatible client pointed at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is missing. "
            "Copy .env.example to .env and fill in your OpenRouter API key."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=REQUEST_TIMEOUT,
        max_retries=1,
    )


def _compiles(source: str) -> bool:
    """Return True if the string is valid Python syntax. Never executes code."""
    try:
        compile(source, "<generated_code>", "exec")
        return True
    except (SyntaxError, ValueError):
        return False


def _clean_code(raw_text: str) -> str:
    """Extract raw code from LLM output."""
    text = raw_text.strip()
    if not text:
        return text

    blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return blocks[-1].strip()

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()

    if _compiles(text):
        return text

    lines = text.splitlines()
    for i in range(len(lines)):
        tail = "\n".join(lines[i:]).strip()
        if tail and _compiles(tail):
            return tail

    return text


def _syntax_errors(code: str) -> List[str]:
    """Compile Python code and return a list of syntax error messages."""
    errors = []
    try:
        compile(code, "<generated_code>", "exec")
    except (SyntaxError, ValueError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return errors


def debug_code(code: str, language: str = "Python") -> str:
    """Inspect code for errors and return corrected code.

    Args:
        code: Source code to check and fix.
        language: Programming language (default Python).

    Returns:
        Corrected source code.

    Raises:
        ValueError: If there is no code to debug or OPENROUTER_API_KEY is not set.
    """
    if not code or not code.strip():
        raise ValueError("No code to debug.")

    is_python = language.lower() == "python"
    errors = _syntax_errors(code) if is_python else []

    if errors:
        user_message = (
            f"The {language} code below has syntax errors. Fix them.\n\n"
            "Detected errors:\n"
            + "\n".join(errors)
            + "\n\nCode:\n\n"
            + code
        )
    else:
        user_message = (
            f"Review this {language} code for logical errors, undefined variables, missing imports/modules, "
            "or edge-case bugs. Fix anything that is wrong.\n\n"
            "Code:\n\n"
            + code
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        from backend.core.llm.model_router import get_model_router
        router = get_model_router()
        if router.is_configured():
            raw = router.generate_text(
                role="debugger",
                messages=messages,
                temperature=0.0,
                timeout=REQUEST_TIMEOUT,
            )
            cleaned = _clean_code(raw)
            if cleaned:
                if is_python and errors:
                    if not _syntax_errors(cleaned):
                        return cleaned
                else:
                    return cleaned
    except Exception:
        pass

    client = _get_client()
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

    last_error = None
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as exc:
            last_error = exc
            continue

        cleaned = _clean_code(response.choices[0].message.content or "")
        if cleaned:
            if is_python and errors:
                if not _syntax_errors(cleaned):
                    return cleaned
            else:
                return cleaned
        last_error = RuntimeError("the model returned no valid code")

    if isinstance(last_error, RuntimeError):
        raise RuntimeError(
            f"Debugger Agent: {last_error} (model={model}). "
            "Try again or change OPENROUTER_MODEL in the .env file."
        )
    raise RuntimeError(
        f"Debugger Agent: OpenRouter request failed (model={model}). {last_error}"
    ) from last_error


from backend.core.base_agent import BaseAgent


class DebuggerAgent(BaseAgent):
    """Diagnoses and repairs code errors."""

    def __init__(self):
        super().__init__(name="Debugger Agent", role="Syntax & Runtime Error Repair", default_llm_role="debugger")

    def debug(self, code: str, language: str = "Python") -> str:
        return debug_code(code, language=language)