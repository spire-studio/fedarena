"""Tests for the code validation logic (no API, pure unit tests)."""

from __future__ import annotations

from apps.backend.app.services.submission import validate_code

from .conftest import VALID_ATTACK_CODE, VALID_DEFENSE_CODE


class TestValidateCode:
    def test_valid_attack(self):
        result = validate_code(VALID_ATTACK_CODE, "attack")
        assert result["ok"] is True
        assert result["method_name"] == "arena_attack_test_atk"
        assert result["class_name"] == "TestAttack"

    def test_valid_defense(self):
        result = validate_code(VALID_DEFENSE_CODE, "defense")
        assert result["ok"] is True
        assert result["method_name"] == "arena_defense_test_def"
        assert result["class_name"] == "TestDefense"

    def test_syntax_error(self):
        result = validate_code("def broken(:", "attack")
        assert result["ok"] is False
        assert "Syntax error" in result["error"]

    def test_no_strategy_class(self):
        result = validate_code("class Foo:\n    pass\n", "attack")
        assert result["ok"] is False
        assert "ResearchAttackStrategy" in result["error"]

    def test_no_method_name(self):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class NoName(ResearchAttackStrategy):
    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""
        result = validate_code(code, "attack")
        assert result["ok"] is False
        assert "method_name" in result["error"]

    def test_wrong_prefix(self):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class Bad(ResearchAttackStrategy):
    method_name = "wrong_prefix"
    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""
        result = validate_code(code, "attack")
        assert result["ok"] is False
        assert "arena_attack_" in result["error"]

    def test_invalid_chars_in_method_name(self):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class Bad(ResearchAttackStrategy):
    method_name = "arena_attack_BAD-name"
    def attack(self, local_model_params, global_model_params, round_num=0, client_id=0):
        return local_model_params
"""
        result = validate_code(code, "attack")
        assert result["ok"] is False
        assert "lowercase" in result["error"]

    def test_missing_required_method_attack(self):
        code = """\
from fl_core.research.base_attack import ResearchAttackStrategy

class Missing(ResearchAttackStrategy):
    method_name = "arena_attack_missing"
    def setup(self, config=None):
        pass
"""
        result = validate_code(code, "attack")
        assert result["ok"] is False
        assert "attack()" in result["error"]

    def test_missing_required_method_defense(self):
        code = """\
from fl_core.research.base_defense import ResearchDefenseStrategy

class Missing(ResearchDefenseStrategy):
    method_name = "arena_defense_missing"
    def setup(self, config=None):
        pass
"""
        result = validate_code(code, "defense")
        assert result["ok"] is False
        assert "aggregate()" in result["error"]

    def test_defense_code_validated_as_attack_fails(self):
        result = validate_code(VALID_DEFENSE_CODE, "attack")
        assert result["ok"] is False
