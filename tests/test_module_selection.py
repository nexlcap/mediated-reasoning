import pytest
from unittest.mock import MagicMock

from src.llm.client import ClaudeClient
from src.llm.prompts import (
    AGENT_SYSTEM_PROMPTS,
    build_dynamic_agent_generation_prompt,
    build_gap_check_prompt,
)
from src.agents.base_agent import create_dynamic_agent


class TestBuildDynamicAgentGenerationPrompt:
    def test_includes_problem_text(self):
        system, user = build_dynamic_agent_generation_prompt("Should we expand into EU?")
        assert "Should we expand into EU?" in user

    def test_system_prompt_describes_role(self):
        system, user = build_dynamic_agent_generation_prompt("test")
        assert "decomposer" in system.lower() or "specialist" in system.lower()

    def test_requests_agents_and_reasoning_fields(self):
        system, user = build_dynamic_agent_generation_prompt("test")
        assert '"agents"' in user
        assert '"reasoning"' in user

    def test_includes_count_guidance(self):
        system, user = build_dynamic_agent_generation_prompt("test")
        assert "3" in user and "7" in user

    def test_includes_snake_case_guidance(self):
        system, user = build_dynamic_agent_generation_prompt("test")
        assert "snake_case" in user


class TestBuildGapCheckPrompt:
    def test_includes_selected_agent_names(self):
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
        assert "ad_hoc_agents" in user
        assert "gaps_identified" in user


class TestCreateDynamicAgent:
    def test_correct_name(self):
        client = MagicMock(spec=ClaudeClient)
        agent = create_dynamic_agent("custom_mod", "You are a custom expert.", client)
        assert agent.name == "custom_mod"

    def test_registers_system_prompt(self):
        client = MagicMock(spec=ClaudeClient)
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        create_dynamic_agent("test_reg_mod", prompt, client)
        assert AGENT_SYSTEM_PROMPTS["test_reg_mod"] == prompt

    def test_round1_works(self):
        client = MagicMock(spec=ClaudeClient)
        client.analyze.return_value = {
            "analysis": {"summary": "test"},
            "flags": [],
            "sources": [],
        }
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        agent = create_dynamic_agent("round1_test_mod", prompt, client)
        output = agent.run_round1("test problem")
        assert output.agent_name == "round1_test_mod"
        assert output.round == 1

    def test_round2_works(self):
        client = MagicMock(spec=ClaudeClient)
        client.analyze.return_value = {
            "analysis": {"summary": "revised"},
            "flags": [],
            "sources": [],
        }
        prompt = "You are a custom expert. Respond with ONLY valid JSON."
        agent = create_dynamic_agent("round2_test_mod", prompt, client)
        output = agent.run_round2("test problem", [])
        assert output.agent_name == "round2_test_mod"
        assert output.round == 2
        assert output.revised is True
