"""
fl_core.research — Pluggable research attack / defense strategies.

Public API
----------
- ``ResearchAttackStrategy``  — base class for attack algorithms
- ``ResearchDefenseStrategy`` — base class for defense algorithms
- ``registry``                — global lookup (get_attack, get_defense, list_*)
"""

from . import registry
from .base_attack import ResearchAttackStrategy
from .base_defense import ResearchDefenseStrategy

__all__ = [
    "ResearchAttackStrategy",
    "ResearchDefenseStrategy",
    "registry",
]
