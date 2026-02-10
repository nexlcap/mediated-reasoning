import threading

import pytest
from unittest.mock import MagicMock, call

from src.llm.client import ClaudeClient
from src.mediator import Mediator
from src.models.schemas import FinalAnalysis
from tests.conftest import SAMPLE_LLM_RESPONSE, SAMPLE_SYNTHESIS_RESPONSE


def _thread_safe_side_effect(responses):
    """Return a side_effect callable that pops from a list in a thread-safe way."""
    lock = threading.Lock()
    queue = list(responses)

    def side_effect(*args, **kwargs):
        with lock:
            item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return side_effect


class TestMediator:
    @pytest.fixture
    def mediator_client(self):
        client = MagicMock(spec=ClaudeClient)
        # First 10 calls (5 round1 + 5 round2) return module output
        # Last call returns synthesis
        responses = [SAMPLE_LLM_RESPONSE] * 10 + [SAMPLE_SYNTHESIS_RESPONSE]
        client.analyze.side_effect = _thread_safe_side_effect(responses)
        return client

    def test_analyze_returns_final_analysis(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert result.problem == sample_problem

    def test_eleven_api_calls(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        mediator.analyze(sample_problem)

        # 5 round1 + 5 round2 + 1 synthesis = 11
        assert mediator_client.analyze.call_count == 11

    def test_module_outputs_collected(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        # 5 round1 + 5 round2 = 10 module outputs
        assert len(result.module_outputs) == 10
        round1 = [o for o in result.module_outputs if o.round == 1]
        round2 = [o for o in result.module_outputs if o.round == 2]
        assert len(round1) == 5
        assert len(round2) == 5

    def test_synthesis_fields_populated(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        assert len(result.conflicts) > 0
        assert result.synthesis != ""
        assert len(result.recommendations) > 0

    def test_graceful_degradation(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        # First module fails, rest succeed
        responses = [Exception("API error")] + [SAMPLE_LLM_RESPONSE] * 4
        # Round 2: only 4 modules run (the failed one is skipped)
        responses += [SAMPLE_LLM_RESPONSE] * 4
        # Synthesis
        responses += [SAMPLE_SYNTHESIS_RESPONSE]
        client.analyze.side_effect = _thread_safe_side_effect(responses)

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        # 4 round1 + 4 round2 = 8 module outputs
        assert len(result.module_outputs) == 8

    def test_total_failure_returns_empty_analysis(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        client.analyze.side_effect = Exception("API error")

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert result.problem == sample_problem
        assert result.module_outputs == []
        assert result.synthesis == ""

    def test_synthesis_failure_returns_partial_result(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        # 5 round1 succeed, 5 round2 succeed, synthesis fails
        responses = [SAMPLE_LLM_RESPONSE] * 10 + [Exception("API error")]
        client.analyze.side_effect = _thread_safe_side_effect(responses)

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert len(result.module_outputs) == 10
        assert result.synthesis == ""
        assert result.conflicts == []
