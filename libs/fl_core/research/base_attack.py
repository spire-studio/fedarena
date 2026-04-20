"""
Abstract base class for research attack strategies.

Subclasses set ``method_name`` as a class variable and implement ``attack()``.
Registration into the global registry happens automatically via
``__init_subclass__``.

Example::

    from fl_core.research.base_attack import ResearchAttackStrategy

    class MyAttack(ResearchAttackStrategy):
        method_name = "arena_attack_my_method"

        def attack(self, local_model_params, global_model_params, **kw):
            # ... your attack logic ...
            return poisoned_params
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import torch

from . import registry

logger = logging.getLogger(__name__)


class ResearchAttackStrategy(ABC):
    """Base class for agent-designed model poisoning attacks.

    The ``attack`` method receives the same information available in the
    existing ``ClientManager.get_client_models`` path so that strategies can
    implement arbitrary poisoning logic.
    """

    method_name: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        name = getattr(cls, "method_name", None)
        # Only register concrete classes that explicitly set method_name
        if name is not None and name != getattr(cls.__bases__[0], "method_name", None):
            registry.register_attack(name, cls)
            logger.debug("Registered attack strategy: %s", name)

    # ------------------------------------------------------------------
    # Optional lifecycle hooks
    # ------------------------------------------------------------------

    def setup(self, config: dict[str, Any] | None = None) -> None:
        """Called once before the first round.  Override to parse config."""

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    @abstractmethod
    def attack(
        self,
        local_model_params: dict[str, torch.Tensor],
        global_model_params: dict[str, torch.Tensor],
        all_client_params: list[dict[str, torch.Tensor]] | None = None,
        round_num: int = 0,
        client_id: int = 0,
        **kwargs: Any,
    ) -> dict[str, torch.Tensor]:
        """Return poisoned model parameters.

        Parameters
        ----------
        local_model_params : dict
            The locally-trained model state dict for this (malicious) client.
        global_model_params : dict
            The current global model state dict (before this round's
            aggregation).
        all_client_params : list of dict, optional
            State dicts from *all* selected clients in this round, if
            available.  May be ``None`` when the attack runs before other
            clients have been collected.
        round_num : int
            Current FL round (1-indexed).
        client_id : int
            ID of the malicious client executing this attack.

        Returns
        -------
        dict
            Poisoned model parameters (same keys as *local_model_params*).
        """
        ...
