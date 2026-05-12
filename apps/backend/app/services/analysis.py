"""LLM-generated analytical reports for arena submissions."""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from ..config import settings

logger = logging.getLogger("fedarena.analysis")

ANALYSIS_SYSTEM_PROMPT = """\
You are FedArena's analysis assistant. Given a submission's evaluation results \
against benchmark opponents, produce a structured analysis report in Markdown.

## Output Structure

1. **Performance Summary** — Overall metrics, how it compares to baselines
2. **Strengths** — Which opponents this method performs best against, with quantitative evidence
3. **Weaknesses** — Which opponents are most problematic, with quantitative evidence
4. **Comparison with Baselines** — How this method ranks among existing baseline methods in the matrix
5. **Key Observations** — Notable patterns in convergence, stability, or accuracy trajectory
6. **Recommendations** — Concrete suggestions for improving the method

## Rules
- Use multi-metric data when available: accuracy_drop, convergence_speed, stability, max_accuracy, runtime
- Be specific — cite actual accuracy values and metric numbers
- For attacks: lower opponent accuracy = stronger attack
- For defenses: higher accuracy under attack = stronger defense
- Keep the report concise but insightful (400-700 words)
- Use Markdown formatting: headers (##), bold, bullet points
- Write in English
"""


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
    )


def _build_analysis_context(
    submission: dict[str, Any],
    results: dict[str, Any],
    matrix_data: dict[str, Any],
) -> str:
    parts: list[str] = []

    parts.append(f"## Submission: {submission.get('display_name', submission.get('method_name'))}")
    parts.append(f"- Role: {submission['role']}")
    parts.append(f"- Method: `{submission['method_name']}`")
    if submission.get("description"):
        parts.append(f"- Description: {submission['description']}")
    parts.append("")

    summary = results.get("__summary__", {})
    if summary:
        parts.append("## Overall Metrics")
        for key, label in [
            ("avg_accuracy", "Avg Accuracy"),
            ("avg_accuracy_drop", "Avg Accuracy Drop"),
            ("worst_case_accuracy", "Worst-Case Accuracy"),
            ("best_case_accuracy", "Best-Case Accuracy"),
            ("avg_convergence_speed", "Avg Convergence Speed (rounds)"),
            ("avg_stability", "Avg Stability (std)"),
            ("avg_runtime_seconds", "Avg Runtime (seconds)"),
        ]:
            if summary.get(key) is not None:
                val = summary[key]
                parts.append(f"- {label}: {val:.4f}" if isinstance(val, float) else f"- {label}: {val}")
        parts.append("")

    parts.append("## Per-Opponent Results")
    parts.append("| Opponent | Accuracy | Acc. Drop | Baseline | Convergence | Stability |")
    parts.append("|----------|----------|-----------|----------|-------------|-----------|")
    for opp, res in results.items():
        if opp == "__summary__":
            continue
        opp_label = opp.replace("__none__", "none").replace("baseline_", "")
        acc = f"{res['avg_final_accuracy']:.4f}" if res.get("avg_final_accuracy") is not None else "FAIL"
        drop = f"{res['accuracy_drop']:.4f}" if res.get("accuracy_drop") is not None else "-"
        base = f"{res['baseline_accuracy']:.4f}" if res.get("baseline_accuracy") is not None else "-"
        conv = f"{res['avg_convergence_speed']:.0f}" if res.get("avg_convergence_speed") is not None else "-"
        stab = f"{res['avg_stability']:.4f}" if res.get("avg_stability") is not None else "-"
        parts.append(f"| {opp_label} | {acc} | {drop} | {base} | {conv} | {stab} |")
    parts.append("")

    matrix = matrix_data.get("matrix", {})
    role = submission["role"]
    if matrix:
        parts.append("## Baseline Reference Matrix (for comparison)")
        if role == "attack":
            parts.append("Baseline attack accuracies (lower = stronger attack):")
            for atk_name, defenses in matrix.items():
                if atk_name == "__none__":
                    continue
                accs = [
                    v.get("avg_final_accuracy") for v in defenses.values() if v.get("avg_final_accuracy") is not None
                ]
                if accs:
                    avg = sum(accs) / len(accs)
                    parts.append(f"- {atk_name}: avg={avg:.4f}")
        else:
            parts.append("Baseline defense accuracies (higher = stronger defense):")
            all_defenses: dict[str, list[float]] = {}
            for _atk, defenses in matrix.items():
                for dfn, vals in defenses.items():
                    if dfn == "__none__":
                        continue
                    acc = vals.get("avg_final_accuracy")
                    if acc is not None:
                        all_defenses.setdefault(dfn, []).append(acc)
            for dfn, accs in all_defenses.items():
                avg = sum(accs) / len(accs)
                parts.append(f"- {dfn}: avg={avg:.4f}")
        parts.append("")

    parts.append("Please analyze this submission's performance and provide insights.")
    return "\n".join(parts)


def _extract_default_scenario_results(results: dict[str, Any]) -> dict[str, Any]:
    """Extract results for analysis — use default scenario from nested format, or flat results."""
    if "scenarios" in results:
        return results["scenarios"].get("cifar10_noniid", next(iter(results["scenarios"].values()), {}))
    return results


async def generate_analysis(
    submission: dict[str, Any],
    results: dict[str, Any],
    matrix_data: dict[str, Any],
) -> str:
    client = _get_client()
    scenario_results = _extract_default_scenario_results(results)
    context = _build_analysis_context(submission, scenario_results, matrix_data)

    response = await client.chat.completions.create(
        model=settings.default_llm_model,
        max_tokens=settings.max_tokens,
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
    )

    return response.choices[0].message.content or ""
