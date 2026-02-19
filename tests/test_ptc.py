"""Unit tests for ClaudeClient.run_ptc_round()."""
import pytest
from unittest.mock import MagicMock

from src.llm.client import ClaudeClient
from src.models.schemas import ModuleOutput
from tests.conftest import SAMPLE_LLM_RESPONSE


def _make_module(name, round1_output=None, round2_output=None, error=None):
    """Create a mock module with the given name and return values."""
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
    return ModuleOutput(
        module_name=name,
        round=round_num,
        analysis=SAMPLE_LLM_RESPONSE["analysis"],
        flags=SAMPLE_LLM_RESPONSE["flags"],
        revised=(round_num == 2),
    )


def _make_tool_use_block(tu_id, module_name):
    block = MagicMock()
    block.type = "tool_use"
    block.id = tu_id
    block.input = {"module_name": module_name}
    return block


def _make_tool_use_response(tu_blocks):
    response = MagicMock()
    response.content = tu_blocks
    response.container = None
    return response


def _make_end_turn_response():
    response = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    response.content = [text_block]
    response.container = None
    return response


class TestRunPtcRound:
    @pytest.fixture
    def ptc_client(self):
        """ClaudeClient with mocked Anthropic SDK internals."""
        client = ClaudeClient()
        client.client = MagicMock()  # replace the anthropic.Anthropic() instance
        return client

    def test_happy_path_round1(self, ptc_client):
        """All modules invoked in parallel via tool_use; results captured in order."""
        m1 = _make_module("market", round1_output=_sample_output("market", 1))
        m2 = _make_module("tech", round1_output=_sample_output("tech", 1))

        tu1 = _make_tool_use_block("tu_1", "market")
        tu2 = _make_tool_use_block("tu_2", "tech")

        ptc_client.client.messages.create.side_effect = [
            _make_tool_use_response([tu1, tu2]),
            _make_end_turn_response(),
        ]

        results = ptc_client.run_ptc_round("test problem", [m1, m2])

        assert len(results) == 2
        assert results[0].module_name == "market"
        assert results[1].module_name == "tech"
        m1.run_round1.assert_called_once_with("test problem", None)
        m2.run_round1.assert_called_once_with("test problem", None)

    def test_partial_failure(self, ptc_client):
        """One module errors; successful modules still returned; failed module absent."""
        m1 = _make_module("market", round1_output=_sample_output("market", 1))
        m2 = _make_module("tech", error=Exception("API timeout"))

        tu1 = _make_tool_use_block("tu_1", "market")
        tu2 = _make_tool_use_block("tu_2", "tech")

        ptc_client.client.messages.create.side_effect = [
            _make_tool_use_response([tu1, tu2]),
            _make_end_turn_response(),
        ]

        results = ptc_client.run_ptc_round("test problem", [m1, m2])

        assert len(results) == 1
        assert results[0].module_name == "market"

    def test_empty_module_list(self, ptc_client):
        """Empty module list: orchestrator returns end_turn immediately, result is []."""
        ptc_client.client.messages.create.return_value = _make_end_turn_response()

        results = ptc_client.run_ptc_round("test problem", [])

        assert results == []

    def test_round2_calls_run_round2(self, ptc_client):
        """With round1_outputs provided, run_round2 is called instead of run_round1."""
        m1 = _make_module("market", round2_output=_sample_output("market", 2))
        round1_dicts = [{"module_name": "market", "round": 1, "analysis": {}, "flags": [], "revised": False, "sources": []}]

        tu1 = _make_tool_use_block("tu_1", "market")

        ptc_client.client.messages.create.side_effect = [
            _make_tool_use_response([tu1]),
            _make_end_turn_response(),
        ]

        results = ptc_client.run_ptc_round("test problem", [m1], round1_outputs=round1_dicts)

        assert len(results) == 1
        assert results[0].module_name == "market"
        assert results[0].round == 2
        m1.run_round2.assert_called_once_with("test problem", round1_dicts, None)
        m1.run_round1.assert_not_called()
