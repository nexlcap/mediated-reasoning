import pytest
from unittest.mock import MagicMock

from src.llm.client import ClaudeClient
from src.llm.prompts import (
    ALL_MODULE_NAMES,
    MODULE_SYSTEM_PROMPTS,
    build_gap_check_prompt,
    build_module_selection_prompt,
)
from src.modules.base_module import create_dynamic_module


class TestBuildModuleSelectionPrompt:
    def test_includes_all_module_names(self):
        system, user = build_module_selection_prompt("test problem")
        for name in ALL_MODULE_NAMES:
            assert name in user

    def test_includes_problem_text(self):
        system, user = build_module_selection_prompt("Should we expand into EU?")
        assert "Should we expand into EU?" in user

    def test_system_prompt_describes_role(self):
        system, user = build_module_selection_prompt("test")
        assert "scoping" in system.lower() or "multi-perspective" in system.lower()

    def test_requests_json_output(self):
        system, user = build_module_selection_prompt("test")
        assert "selected_modules" in user
        assert "reasoning" in user


class TestBuildGapCheckPrompt:
    def test_includes_selected_modules(self):
        selected = ["market", "tech", "cost"]
        system, user = build_gap_check_prompt("test problem", selected)
        for name in selected:
            assert name in user

    def test_includes_problem_text(self):
        system, user = build_gap_check_prompt("Build a new app", ["market"])
        assert "Build a new app" in user

    def test_lists_all_available_modules(self):
        system, user = build_gap_check_prompt("test", ["market"])
        for name in ALL_MODULE_NAMES:
            assert name in user

    def test_requests_json_output(self):
        system, user = build_gap_check_prompt("test", ["market"])
        assert "ad_hoc_modules" in user
        assert "gaps_identified" in user


class TestCreateDynamicModule:
    def test_correct_name(self):
        client = MagicMock(spec=ClaudeClient)
        module = create_dynamic_module("custom_mod", "You are a custom expert.", client)
        assert module.name == "custom_mod"

    def test_registers_system_prompt(self):
        client = MagicMock(spec=ClaudeClient)
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        create_dynamic_module("test_reg_mod", prompt, client)
        assert MODULE_SYSTEM_PROMPTS["test_reg_mod"] == prompt

    def test_round1_works(self):
        client = MagicMock(spec=ClaudeClient)
        client.analyze.return_value = {
            "analysis": {"summary": "test"},
            "flags": [],
            "sources": [],
        }
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        module = create_dynamic_module("round1_test_mod", prompt, client)
        output = module.run_round1("test problem")
        assert output.module_name == "round1_test_mod"
        assert output.round == 1

    def test_round2_works(self):
        client = MagicMock(spec=ClaudeClient)
        client.analyze.return_value = {
            "analysis": {"summary": "revised"},
            "flags": [],
            "sources": [],
        }
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        module = create_dynamic_module("round2_test_mod", prompt, client)
        output = module.run_round2("test problem", [])
        assert output.module_name == "round2_test_mod"
        assert output.round == 2
        assert output.revised is True
