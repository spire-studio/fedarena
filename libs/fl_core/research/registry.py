"""
Global registry for research attack and defense strategies.

Strategies register themselves automatically via __init_subclass__ when they
define a ``method_name`` class variable.  The registry also provides helpers
to discover strategy modules on disk and import them lazily.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_attack import ResearchAttackStrategy
    from .base_defense import ResearchDefenseStrategy

logger = logging.getLogger(__name__)

_ATTACK_REGISTRY: dict[str, type[ResearchAttackStrategy]] = {}
_DEFENSE_REGISTRY: dict[str, type[ResearchDefenseStrategy]] = {}


# ------------------------------------------------------------------
# Registration helpers (called by base class __init_subclass__)
# ------------------------------------------------------------------


def register_attack(name: str, cls: type[ResearchAttackStrategy]) -> None:
    if name in _ATTACK_REGISTRY:
        logger.debug("Overwriting attack registry entry: %s", name)
    _ATTACK_REGISTRY[name] = cls


def register_defense(name: str, cls: type[ResearchDefenseStrategy]) -> None:
    if name in _DEFENSE_REGISTRY:
        logger.debug("Overwriting defense registry entry: %s", name)
    _DEFENSE_REGISTRY[name] = cls


# ------------------------------------------------------------------
# Lookup helpers
# ------------------------------------------------------------------


def get_attack(name: str) -> type[ResearchAttackStrategy]:
    _ensure_discovered()
    if name not in _ATTACK_REGISTRY:
        raise KeyError(f"Unknown attack strategy '{name}'. Available: {list(_ATTACK_REGISTRY)}")
    return _ATTACK_REGISTRY[name]


def get_defense(name: str) -> type[ResearchDefenseStrategy]:
    _ensure_discovered()
    if name not in _DEFENSE_REGISTRY:
        raise KeyError(f"Unknown defense strategy '{name}'. Available: {list(_DEFENSE_REGISTRY)}")
    return _DEFENSE_REGISTRY[name]


def list_attacks() -> list[str]:
    _ensure_discovered()
    return sorted(_ATTACK_REGISTRY)


def list_defenses() -> list[str]:
    _ensure_discovered()
    return sorted(_DEFENSE_REGISTRY)


# ------------------------------------------------------------------
# Auto-discovery
# ------------------------------------------------------------------

_discovered = False


def _ensure_discovered() -> None:
    global _discovered
    if _discovered:
        return
    _discovered = True
    _discover_packages()


def _discover_packages() -> None:
    """Walk ``attacks/`` and ``defenses/`` sub-trees and import every Python
    package that looks like it contains a strategy (i.e. has ``__init__.py``).

    This triggers the ``__init_subclass__`` hook which populates the registry.
    """
    research_root = Path(__file__).resolve().parent

    for sub in ("attacks", "defenses"):
        sub_dir = research_root / sub
        if not sub_dir.is_dir():
            continue

        # Import the sub-package itself first so relative imports work
        sub_pkg = f"fl_core.research.{sub}"
        try:
            importlib.import_module(sub_pkg)
        except Exception:
            logger.debug("Could not import %s", sub_pkg, exc_info=True)

        # Walk all nested packages
        for importer, modname, ispkg in pkgutil.walk_packages(
            path=[str(sub_dir)],
            prefix=f"{sub_pkg}.",
        ):
            try:
                importlib.import_module(modname)
            except Exception:
                logger.debug("Could not import %s", modname, exc_info=True)
