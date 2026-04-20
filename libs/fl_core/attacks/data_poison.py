import logging
from typing import Any

import numpy as np


class DataPoisonAttack:
    def __init__(self, attack_config: dict[str, Any]):
        self.attack_config = attack_config
        self.attack_type = attack_config.get("attack_type", "label_flipping")
        self.attack_params = attack_config.get("attack_params", {})
        self.malicious_clients = attack_config.get("malicious_clients", [])

        self._validate_attack_params()

        self.logger = logging.getLogger(__name__)

    def _validate_attack_params(self):
        if self.attack_type == "label_flipping":
            flip_ratio = self.attack_params.get("flip_ratio", 0.1)
            if not 0 <= flip_ratio <= 1:
                raise ValueError(f"flip_ratio must be between 0 and 1, got {flip_ratio}")

        if not isinstance(self.malicious_clients, list):
            raise ValueError("malicious_clients must be a list")

        for client_id in self.malicious_clients:
            if not isinstance(client_id, int) or client_id < 0:
                raise ValueError(f"Invalid malicious client ID: {client_id}")

    def is_malicious_client(self, client_id: int) -> bool:
        return client_id in self.malicious_clients

    def label_flipping(
        self, data: np.ndarray, labels: np.ndarray, flip_ratio: float | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        if flip_ratio is None:
            flip_ratio = self.attack_params.get("flip_ratio", 0.1)

        if not 0 <= flip_ratio <= 1:
            raise ValueError(f"flip_ratio must be between 0 and 1, got {flip_ratio}")

        poisoned_data = data.copy()
        poisoned_labels = labels.copy()

        num_samples = len(labels)
        num_flip = int(num_samples * flip_ratio)

        if num_flip > 0:
            flip_indices = np.random.choice(num_samples, num_flip, replace=False)

            unique_labels = np.unique(labels)

            for idx in flip_indices:
                original_label = poisoned_labels[idx]
                possible_labels = [label for label in unique_labels if label != original_label]
                if possible_labels:
                    poisoned_labels[idx] = np.random.choice(possible_labels)

            self.logger.info(
                f"Label flipping attack: flipped {num_flip}/{num_samples} labels (ratio: {flip_ratio:.2f})"
            )

        return poisoned_data, poisoned_labels

    def apply_attack(
        self,
        client_id: int,
        data: np.ndarray,
        labels: np.ndarray,
        override_type: str | None = None,
        override_params: dict | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:

        # 确定本次攻击要使用的类型和参数
        attack_type = override_type if override_type else self.attack_type
        params = override_params if override_params else self.attack_params

        self.logger.info(f"正在对客户端 {client_id} 执行 {attack_type} 攻击 (异构配置)")

        if attack_type == "label_flipping":
            return self.label_flipping(data, labels, flip_ratio=params.get("flip_ratio"))
        else:
            self.logger.warning(f"未知攻击类型: {attack_type}")
            return data, labels

    def get_attack_info(self) -> dict[str, Any]:
        return {
            "attack_type": self.attack_type,
            "attack_params": self.attack_params,
            "malicious_clients": self.malicious_clients,
            "num_malicious_clients": len(self.malicious_clients),
        }


class DataAttackManager:
    def __init__(self, attack_config: dict[str, Any]):
        self.attack_config = attack_config
        self.attack_enabled = attack_config.get("enable", False)

        if self.attack_enabled:
            self.data_poison_attack = DataPoisonAttack(attack_config)
        else:
            self.data_poison_attack = None

        self.logger = logging.getLogger(__name__)

    def is_attack_enabled(self) -> bool:
        return self.attack_enabled

    def is_malicious_client(self, client_id: int) -> bool:
        if not self.attack_enabled or self.data_poison_attack is None:
            return False
        return self.data_poison_attack.is_malicious_client(client_id)

    def apply_data_poison_attack(
        self,
        client_id: int,
        data: np.ndarray,
        labels: np.ndarray,
        override_type: str | None = None,
        override_params: dict | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        if not self.attack_enabled or self.data_poison_attack is None:
            return data, labels

        return self.data_poison_attack.apply_attack(
            client_id, data, labels, override_type=override_type, override_params=override_params
        )

    def get_attack_summary(self) -> dict[str, Any]:
        if not self.attack_enabled or self.data_poison_attack is None:
            return {"attack_enabled": False}

        summary = {"attack_enabled": True}
        summary.update(self.data_poison_attack.get_attack_info())
        return summary
