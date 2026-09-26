"""Generator Agent.

This agent receives a natural-language programming requirement from the user
and asks the LLM to generate code that fulfils it. Supports multi-language generation.
"""

import os
import re
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = "openrouter/free"
REQUEST_TIMEOUT = 45.0

SYSTEM_PROMPT_PYTHON = (
    "You are a senior Python code generator. "
    "You receive a programming requirement written in plain English. "
    "Your job is to write clean, correct Python code that fulfils the requirement. "
    "Return ONLY the raw Python code inside Markdown code fences or clean text. "
    "Do NOT add explanations or prose outside the code."
)

SYSTEM_PROMPT_GENERIC = (
    "You are a senior software engineer. "
    "You receive a programming requirement written in plain English. "
    "Your job is to write clean, correct code in the requested language that fulfils the requirement. "
    "Return ONLY the raw code inside Markdown code fences or clean text. "
    "Do NOT add explanations or prose outside the code."
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
    """Extract raw code from LLM output.

    1. content of the last fenced block (```python, ```js, etc.), if present;
    2. the whole text, if it is already valid Python or clean code;
    3. stripped text fallback.
    """
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


def generate_code(requirement: str, language: str = "Python") -> str:
    """Turn a natural-language requirement into source code.

    Args:
        requirement: Plain-English description of the program to build.
        language: Target programming language (defaults to Python).

    Returns:
        A string containing only the generated source code.

    Raises:
        ValueError: If no requirement is given or OPENROUTER_API_KEY is not set.
    """
    if not requirement or not requirement.strip():
        raise ValueError("Please provide a programming requirement.")

    sys_prompt = SYSTEM_PROMPT_PYTHON if language.lower() == "python" else SYSTEM_PROMPT_GENERIC
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Language: {language}\nRequirement: {requirement.strip()}"},
    ]

    try:
        from backend.core.llm.model_router import get_model_router
        router = get_model_router()
        if router.is_configured():
            raw = router.generate_text(
                role="coder",
                messages=messages,
                temperature=0.2,
                timeout=REQUEST_TIMEOUT,
            )
            code = _clean_code(raw)
            if code:
                if language.lower() == "python":
                    if _compiles(code):
                        return code
                else:
                    return code
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
                temperature=0.2,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as exc:
            last_error = exc
            continue

        code = _clean_code(response.choices[0].message.content or "")
        if code:
            if language.lower() == "python":
                if _compiles(code):
                    return code
            else:
                return code
        last_error = RuntimeError("the model returned no valid code")

    if isinstance(last_error, RuntimeError):
        raise RuntimeError(
            f"Generator Agent: {last_error} (model={model}). "
            "Try again or change OPENROUTER_MODEL in the .env file."
        )
    raise RuntimeError(
        f"Generator Agent: OpenRouter request failed (model={model}). {last_error}"
    ) from last_error