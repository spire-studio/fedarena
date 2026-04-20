"""LLM-based code generation service for arena submissions."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from ...config import settings
from .prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger("fedarena.agent.codegen")


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )


async def generate_submission(user_prompt: str) -> dict[str, Any]:
    """Call the LLM to generate attack/defense code from a natural language description.

    Returns a dict with keys: role, method_name, class_name, display_name, description, code.
    Raises ValueError on parse failure.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.default_llm_model,
        max_tokens=settings.max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(user_prompt)},
        ],
    )

    raw = response.choices[0].message.content or ""
    logger.debug("LLM response: %s", raw[:500])

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw response:\n{raw[:500]}") from e

    # Validate required fields
    required = {"role", "method_name", "class_name", "code"}
    missing = required - set(result.keys())
    if missing:
        raise ValueError(f"LLM response missing fields: {missing}")

    if result["role"] not in ("attack", "defense"):
        raise ValueError(f"Invalid role: {result['role']}")

    return result
