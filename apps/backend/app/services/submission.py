"""Submission validation and file management."""

from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SUBMISSIONS_ROOT = PROJECT_ROOT / "libs" / "fl_core" / "research"


def validate_code(code: str, role: str) -> dict[str, Any]:
    """Validate submitted code. Returns {ok: bool, error?: str, method_name?: str}."""
    # 1. Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "error": f"Syntax error: {e}"}

    # 2. Find class that inherits from ResearchAttackStrategy / ResearchDefenseStrategy
    expected_base = "ResearchAttackStrategy" if role == "attack" else "ResearchDefenseStrategy"
    strategy_class = None
    method_name = None

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.append(base.attr)
            if expected_base in base_names:
                strategy_class = node.name
                # Extract method_name from class body
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id == "method_name":
                                if isinstance(item.value, ast.Constant):
                                    method_name = item.value.value
                break

    if not strategy_class:
        return {
            "ok": False,
            "error": f"No class inheriting from {expected_base} found",
        }

    if not method_name:
        return {"ok": False, "error": "No method_name class variable found"}

    # 3. Validate method_name format
    prefix = "arena_attack_" if role == "attack" else "arena_defense_"
    if not method_name.startswith(prefix):
        return {
            "ok": False,
            "error": f"method_name must start with '{prefix}', got '{method_name}'",
        }

    if not re.match(r"^[a-z0-9_]+$", method_name):
        return {
            "ok": False,
            "error": "method_name must only contain lowercase letters, digits, and underscores",
        }

    # 4. Check required method exists
    required_method = "attack" if role == "attack" else "aggregate"
    has_method = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == required_method
        for node in ast.walk(tree)
    )
    if not has_method:
        return {
            "ok": False,
            "error": f"Class must implement '{required_method}()' method",
        }

    return {"ok": True, "method_name": method_name, "class_name": strategy_class}


def write_submission_files(method_name: str, class_name: str, role: str, code: str) -> Path:
    """Write strategy.py and __init__.py to the submissions directory."""
    sub_type = "attacks" if role == "attack" else "defenses"
    # Extract short name from method_name (strip arena_attack_ / arena_defense_ prefix)
    prefix = "arena_attack_" if role == "attack" else "arena_defense_"
    short_name = method_name[len(prefix) :]

    sub_dir = SUBMISSIONS_ROOT / sub_type / "submissions" / short_name
    sub_dir.mkdir(parents=True, exist_ok=True)

    # Write strategy.py
    (sub_dir / "strategy.py").write_text(code, encoding="utf-8")

    # Write __init__.py
    init_content = textwrap.dedent(f"""\
        from .strategy import {class_name}

        __all__ = ["{class_name}"]
    """)
    (sub_dir / "__init__.py").write_text(init_content, encoding="utf-8")

    return sub_dir


def compute_versioned_name(group: str, version: int) -> str:
    """Return the actual method_name for a given group and version."""
    if version <= 1:
        return group
    return f"{group}_v{version}"


def rewrite_method_name_in_code(code: str, old_name: str, new_name: str) -> str:
    """Replace method_name assignment value in strategy code."""
    return re.sub(
        r'(method_name\s*=\s*["\'])' + re.escape(old_name) + r'(["\'])',
        r"\g<1>" + new_name + r"\2",
        code,
    )


def remove_submission_files(method_name: str, role: str) -> None:
    """Remove submission directory."""
    import shutil

    sub_type = "attacks" if role == "attack" else "defenses"
    prefix = "arena_attack_" if role == "attack" else "arena_defense_"
    short_name = method_name[len(prefix) :]

    sub_dir = SUBMISSIONS_ROOT / sub_type / "submissions" / short_name
    if sub_dir.is_dir():
        shutil.rmtree(sub_dir)
