"""Unit tests for ClaudeClient.run_ptc_round()."""
import json
import pytest
from unittest.mock import MagicMock, patch

from src.llm.client import ClaudeClient
from src.models.schemas import AgentOutput
from tests.conftest import SAMPLE_LLM_RESPONSE


def _make_agent(name, round1_output=None, round2_output=None, error=None):
    """Create a mock agent with the given name and return values."""
    m = MagicMock()
    m.name = name
    if error:
        m.run_round1.side_effect = error
        m.run_round2.side_effect = error
    else:
        if round1_output is not None:
            m.run_round1.return_value = round1_output
        if round2_output is not None:
            m.run_round2.return_value = round2_output
    return m


def _sample_output(name, round_num):
    return AgentOutput(
        agent_name=name,
        round=round_num,
        analysis=SAMPLE_LLM_RESPONSE["analysis"],
        flags=SAMPLE_LLM_RESPONSE["flags"],
        revised=(round_num == 2),
    )


def _make_tool_call(tc_id, agent_name):
    """Build an OpenAI-style tool_call mock (as returned by LiteLLM)."""
    tc = MagicMock()
    tc.id = tc_id
    tc.function.name = "analyze_agent"
    tc.function.arguments = json.dumps({"agent_name": agent_name})
    return tc


def _make_tool_response(tool_calls):
    """Build an OpenAI-style response mock with tool calls."""
    response = MagicMock()
    response.choices[0].message.tool_calls = tool_calls
    response.choices[0].message.content = ""
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    return response


def _make_end_turn_response():
    """Build an OpenAI-style response mock with no tool calls (end of loop)."""
    response = MagicMock()
    response.choices[0].message.tool_calls = []
    response.choices[0].message.content = "Done."
    response.usage.prompt_tokens = 50
    response.usage.completion_tokens = 10
    return response


class TestRunPtcRound:
    @pytest.fixture
    def ptc_client(self):
        """ClaudeClient for PTC tests (litellm.completion will be patched per test)."""
        return ClaudeClient()

    def test_happy_path_round1(self, ptc_client):
        """All agents invoked in parallel via tool_calls; results captured in order."""
        m1 = _make_agent("market", round1_output=_sample_output("market", 1))
        m2 = _make_agent("tech", round1_output=_sample_output("tech", 1))

        tc1 = _make_tool_call("tc_1", "market")
        tc2 = _make_tool_call("tc_2", "tech")

        with patch("src.llm.client.litellm.completion", side_effect=[
            _make_tool_response([tc1, tc2]),
            _make_end_turn_response(),
        ]):
            results = ptc_client.run_ptc_round("test problem", [m1, m2])

        assert len(results) == 2
        assert results[0].agent_name == "market"
        assert results[1].agent_name == "tech"
        m1.run_round1.assert_called_once_with("test problem", None)
        m2.run_round1.assert_called_once_with("test problem", None)

    def test_partial_failure(self, ptc_client):
        """One agent errors; successful agents still returned; failed agent absent."""
        m1 = _make_agent("market", round1_output=_sample_output("market", 1))
        m2 = _make_agent("tech", error=Exception("API timeout"))

        tc1 = _make_tool_call("tc_1", "market")
        tc2 = _make_tool_call("tc_2", "tech")

        with patch("src.llm.client.litellm.completion", side_effect=[
            _make_tool_response([tc1, tc2]),
            _make_end_turn_response(),
        ]):
            results = ptc_client.run_ptc_round("test problem", [m1, m2])

        assert len(results) == 1
        assert results[0].agent_name == "market"

    def test_empty_agent_list(self, ptc_client):
        """Empty agent list: orchestrator returns end_turn immediately, result is []."""
        with patch("src.llm.client.litellm.completion", return_value=_make_end_turn_response()):
            results = ptc_client.run_ptc_round("test problem", [])

        assert results == []

    def test_round2_calls_run_round2(self, ptc_client):
        """With round1_outputs provided, run_round2 is called instead of run_round1."""
        m1 = _make_agent("market", round2_output=_sample_output("market", 2))
        round1_dicts = [{"agent_name": "market", "round": 1, "analysis": {}, "flags": [], "revised": False, "sources": []}]

        tc1 = _make_tool_call("tc_1", "market")

        with patch("src.llm.client.litellm.completion", side_effect=[
            _make_tool_response([tc1]),
            _make_end_turn_response(),
        ]):
            results = ptc_client.run_ptc_round("test problem", [m1], round1_outputs=round1_dicts)

        assert len(results) == 1
        assert results[0].agent_name == "market"
        assert results[0].round == 2
        m1.run_round2.assert_called_once_with("test problem", round1_dicts, None)
        m1.run_round1.assert_not_called()
