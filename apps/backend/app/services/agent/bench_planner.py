"""LLM-based experiment planner for bench mode."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from ...config import settings
from .bench_prompts import BENCH_SYSTEM_PROMPT, build_bench_user_prompt

logger = logging.getLogger("fedarena.agent.bench")


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )


async def plan_experiments(user_prompt: str) -> dict[str, Any]:
    """Call the LLM to parse a natural language request into experiment plans.

    Returns {"plan_summary": str, "experiments": [{"name", "attack_method", "defense_method"}, ...]}.
    """
    client = _get_client()

    response = await client.chat.completions.create(
        model=settings.default_llm_model,
        max_tokens=settings.max_tokens,
        messages=[
            {"role": "system", "content": BENCH_SYSTEM_PROMPT},
            {"role": "user", "content": build_bench_user_prompt(user_prompt)},
        ],
    )

    raw = response.choices[0].message.content or ""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw[:500]}") from e

    experiments = result.get("experiments", [])
    if not isinstance(experiments, list) or not experiments:
        raise ValueError(f"LLM returned no experiments. Raw: {raw[:500]}")

    # Normalize
    for exp in experiments:
        if not exp.get("name"):
            atk = exp.get("attack_method") or "none"
            dfn = exp.get("defense_method") or "fedavg"
            exp["name"] = f"{atk}_vs_{dfn}"

    return {
        "plan_summary": result.get("plan_summary", ""),
        "experiments": experiments,
    }
