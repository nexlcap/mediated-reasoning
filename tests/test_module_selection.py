import pytest
from unittest.mock import MagicMock

from src.llm.client import ClaudeClient
from src.llm.prompts import (
    MODULE_SYSTEM_PROMPTS,
    build_dynamic_module_generation_prompt,
    build_gap_check_prompt,
)
from src.modules.base_module import create_dynamic_module


class TestBuildDynamicModuleGenerationPrompt:
    def test_includes_problem_text(self):
        system, user = build_dynamic_module_generation_prompt("Should we expand into EU?")
        assert "Should we expand into EU?" in user

    def test_system_prompt_describes_role(self):
        system, user = build_dynamic_module_generation_prompt("test")
        assert "decomposer" in system.lower() or "specialist" in system.lower()

    def test_requests_modules_and_reasoning_fields(self):
        system, user = build_dynamic_module_generation_prompt("test")
        assert '"modules"' in user
        assert '"reasoning"' in user

    def test_includes_count_guidance(self):
        system, user = build_dynamic_module_generation_prompt("test")
        assert "3" in user and "7" in user

    def test_includes_snake_case_guidance(self):
        system, user = build_dynamic_module_generation_prompt("test")
        assert "snake_case" in user


class TestBuildGapCheckPrompt:
    def test_includes_selected_module_names(self):
        selected = [
            {"name": "market_dynamics", "system_prompt": "You are a market dynamics expert. Respond with ONLY valid JSON, no other text."},
            {"name": "tech_feasibility", "system_prompt": "You are a tech feasibility expert. Respond with ONLY valid JSON, no other text."},
        ]
        system, user = build_gap_check_prompt("test problem", selected)
        assert "market_dynamics" in user
        assert "tech_feasibility" in user

    def test_includes_problem_text(self):
        selected = [{"name": "market", "system_prompt": "You are a market expert. Respond with ONLY valid JSON, no other text."}]
        system, user = build_gap_check_prompt("Build a new app", selected)
        assert "Build a new app" in user

    def test_requests_json_output(self):
        selected = [{"name": "market", "system_prompt": "You are a market expert. Respond with ONLY valid JSON, no other text."}]
        system, user = build_gap_check_prompt("test", selected)
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
