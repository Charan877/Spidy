"""Documentation Agent.

This agent receives source code and adds useful docstrings, comments,
and documentation while preserving functionality. Supports multi-language code.
"""

import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "openrouter/free"
REQUEST_TIMEOUT = 45.0

SYSTEM_PROMPT = (
    "You are a software documentation expert. "
    "You receive working code. "
    "Add useful docstrings, comments, and improve readability where appropriate. "
    "Do NOT change the behavior or logic of the program. "
    "Return ONLY the final raw code inside Markdown code fences or clean text. "
    "Do NOT add any text outside the code."
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


def document_code(code: str, language: str = "Python") -> str:
    """Document code with docstrings and comments.

    Args:
        code: Source code to document.
        language: Target programming language (default Python).

    Returns:
        The documented source code (functionality preserved).

    Raises:
        ValueError: If there is no code to document or OPENROUTER_API_KEY is not set.
    """
    if not code or not code.strip():
        raise ValueError("No code to document.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Language: {language}\nCode:\n{code}"},
    ]

    try:
        from backend.core.llm.model_router import get_model_router
        router = get_model_router()
        if router.is_configured():
            raw = router.generate_text(
                role="general",
                messages=messages,
                temperature=0.1,
                timeout=REQUEST_TIMEOUT,
            )
            result = _clean_code(raw)
            if result:
                if language.lower() == "python":
                    if _compiles(result):
                        return result
                else:
                    return result
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
                temperature=0.1,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as exc:
            last_error = exc
            continue

        result = _clean_code(response.choices[0].message.content or "")
        if result:
            if language.lower() == "python":
                if _compiles(result):
                    return result
            else:
                return result
        last_error = RuntimeError("the model returned no valid code")

    if isinstance(last_error, RuntimeError):
        raise RuntimeError(
            f"Documentation Agent: {last_error} (model={model}). "
            "Try again or change OPENROUTER_MODEL in the .env file."
        )
    raise RuntimeError(
        f"Documentation Agent: OpenRouter request failed (model={model}). {last_error}"
    ) from last_error