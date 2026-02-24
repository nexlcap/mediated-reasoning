import pytest
from unittest.mock import MagicMock, patch

from src.llm.client import ClaudeClient
from src.mediator import Mediator
from src.models.schemas import FinalAnalysis, AgentOutput, TokenUsage
from tests.conftest import SAMPLE_LLM_RESPONSE, SAMPLE_SYNTHESIS_RESPONSE, _fake_ptc_round

SAMPLE_SYNTHESIS_WITH_DISCLAIMER = {
    **SAMPLE_SYNTHESIS_RESPONSE,
    "deactivated_disclaimer": "The cost agent was deactivated and its perspective is not reflected.",
}


def _make_ptc_client(synthesis_response=None):
    """Create a MagicMock ClaudeClient configured for PTC tests.

    run_ptc_round is stubbed with _fake_ptc_round (returns AgentOutputs directly).
    analyze returns synthesis_response (defaults to SAMPLE_SYNTHESIS_RESPONSE).
    token_usage returns a real TokenUsage() so Pydantic validation passes.
    """
    client = MagicMock(spec=ClaudeClient)
    client.run_ptc_round.side_effect = _fake_ptc_round
    client.analyze.return_value = synthesis_response or SAMPLE_SYNTHESIS_RESPONSE
    client.token_usage.return_value = TokenUsage()
    return client


class TestMediator:
    @pytest.fixture
    def mediator_client(self):
        return _make_ptc_client()

    def test_analyze_returns_final_analysis(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert result.problem == sample_problem

    def test_ptc_and_synthesis_calls(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        mediator.analyze(sample_problem)

        # run_ptc_round called twice (R1 and R2), analyze called once (synthesis)
        assert mediator_client.run_ptc_round.call_count == 2
        assert mediator_client.analyze.call_count == 1

    def test_agent_outputs_collected(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        # 6 round1 + 6 round2 = 12 agent outputs
        assert len(result.agent_outputs) == 12
        round1 = [o for o in result.agent_outputs if o.round == 1]
        round2 = [o for o in result.agent_outputs if o.round == 2]
        assert len(round1) == 6
        assert len(round2) == 6

    def test_synthesis_fields_populated(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        assert len(result.conflicts) > 0
        assert result.conflicts[0].agents == ["market", "cost"]
        assert result.conflicts[0].topic == "burn rate"
        assert result.conflicts[0].severity == "high"
        assert result.synthesis != ""
        assert len(result.recommendations) > 0

    def test_graceful_degradation(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()

        # R1 returns only 2 agents (market failed inside PTC)
        call_count = [0]
        def _partial_ptc(problem, agents, round1_outputs=None, searcher=None):
            call_count[0] += 1
            round_num = 2 if round1_outputs is not None else 1
            # R1: skip first agent (simulates one agent failing inside run_ptc_round)
            effective = agents if round_num == 2 else agents[1:]
            return [
                AgentOutput(
                    agent_name=m.name,
                    round=round_num,
                    analysis=SAMPLE_LLM_RESPONSE["analysis"],
                    flags=SAMPLE_LLM_RESPONSE["flags"],
                    revised=(round_num == 2),
                )
                for m in effective
            ]

        client.run_ptc_round.side_effect = _partial_ptc
        client.analyze.return_value = SAMPLE_SYNTHESIS_RESPONSE

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        # 5 round1 (1 skipped) + 5 round2 (only R1 survivors) = 10 agent outputs
        assert len(result.agent_outputs) == 10

    def test_total_failure_returns_empty_analysis(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.run_ptc_round.side_effect = Exception("API error")

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert result.problem == sample_problem
        assert result.agent_outputs == []
        assert result.synthesis == ""

    def test_synthesis_failure_returns_partial_result(self, sample_problem):
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.run_ptc_round.side_effect = _fake_ptc_round
        client.analyze.side_effect = Exception("API error")

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result, FinalAnalysis)
        assert len(result.agent_outputs) == 12
        assert result.synthesis == ""
        assert result.conflicts == []

    def test_sources_collected(self, mediator_client, sample_problem):
        mediator = Mediator(mediator_client)
        result = mediator.analyze(sample_problem)

        assert isinstance(result.sources, list)
        assert len(result.sources) > 0
        # Agent sources + synthesis sources, deduplicated and prefix-stripped
        for s in SAMPLE_LLM_RESPONSE["sources"]:
            assert s in result.sources
        for s in SAMPLE_SYNTHESIS_RESPONSE["sources"]:
            assert s in result.sources
        # Agent outputs have sources cleared (consolidated at top level)
        for output in result.agent_outputs:
            assert output.sources == []


class TestMediatorWeights:
    def test_weight_zero_deactivates_agent(self, sample_problem):
        client = _make_ptc_client(synthesis_response=SAMPLE_SYNTHESIS_WITH_DISCLAIMER)

        mediator = Mediator(client, weights={"cost": 0})
        result = mediator.analyze(sample_problem)

        # run_ptc_round called for R1 + R2; analyze called for synthesis only
        assert client.run_ptc_round.call_count == 2
        assert client.analyze.call_count == 1
        agent_names = {o.agent_name for o in result.agent_outputs}
        assert "cost" not in agent_names
        assert len(agent_names) == 5

    def test_deactivated_agents_tracked(self):
        client = _make_ptc_client()
        mediator = Mediator(client, weights={"cost": 0, "risk": 0})
        assert set(mediator.deactivated_agents) == {"cost", "risk"}
        assert len(mediator.agents) == 4

    def test_weight_nonzero_keeps_agent(self):
        client = _make_ptc_client()
        mediator = Mediator(client, weights={"risk": 2})
        assert mediator.deactivated_agents == []
        assert len(mediator.agents) == 6

    def test_disclaimer_passed_through(self, sample_problem):
        client = _make_ptc_client(synthesis_response=SAMPLE_SYNTHESIS_WITH_DISCLAIMER)

        mediator = Mediator(client, weights={"cost": 0})
        result = mediator.analyze(sample_problem)

        assert "cost" in result.deactivated_disclaimer.lower()

    def test_no_disclaimer_without_deactivation(self, sample_problem):
        client = _make_ptc_client()

        mediator = Mediator(client, weights={"risk": 2})
        result = mediator.analyze(sample_problem)

        assert result.deactivated_disclaimer == ""

    def test_weights_passed_to_synthesis_prompt(self, sample_problem):
        client = _make_ptc_client(synthesis_response=SAMPLE_SYNTHESIS_WITH_DISCLAIMER)

        mediator = Mediator(client, weights={"cost": 0, "risk": 2})
        with patch("src.mediator.build_synthesis_prompt", wraps=__import__("src.llm.prompts", fromlist=["build_synthesis_prompt"]).build_synthesis_prompt) as mock_prompt:
            mediator.analyze(sample_problem)
            _, kwargs = mock_prompt.call_args
            assert kwargs["weights"] == {"cost": 0, "risk": 2}
            assert kwargs["deactivated_agents"] == ["cost"]

    def test_default_no_weights(self):
        client = _make_ptc_client()
        mediator = Mediator(client)
        assert mediator.weights == {}
        assert mediator.deactivated_agents == []
        assert len(mediator.agents) == 6



SAMPLE_GENERATION_RESPONSE = {
    "agents": [
        {"name": "market_dynamics", "system_prompt": "You are a market dynamics expert. Respond with ONLY valid JSON, no other text."},
        {"name": "technical_feasibility", "system_prompt": "You are a technical feasibility expert. Respond with ONLY valid JSON, no other text."},
        {"name": "unit_economics", "system_prompt": "You are a unit economics expert. Respond with ONLY valid JSON, no other text."},
    ],
    "reasoning": "These three cover demand, technical, and financial dimensions.",
}

SAMPLE_GAP_CHECK_NO_GAPS = {
    "gaps_identified": False,
    "reasoning": "Coverage is sufficient.",
    "ad_hoc_agents": [],
}

SAMPLE_GAP_CHECK_WITH_ADHOC = {
    "gaps_identified": True,
    "reasoning": "Missing cultural perspective.",
    "ad_hoc_agents": [
        {"name": "cultural", "system_prompt": "You are a cultural expert. Respond with ONLY valid JSON."},
    ],
}

SAMPLE_GAP_CHECK_5_ADHOC = {
    "gaps_identified": True,
    "reasoning": "Many gaps.",
    "ad_hoc_agents": [
        {"name": f"adhoc{i}", "system_prompt": f"Expert {i}. Respond with ONLY valid JSON."}
        for i in range(5)
    ],
}

SAMPLE_GENERATION_MALFORMED = {
    "agents": [
        {"name": "market_dynamics", "system_prompt": "You are a market dynamics expert. Respond with ONLY valid JSON, no other text."},
        {"name": "", "system_prompt": "Missing name — should be skipped"},
        {"system_prompt": "No name key at all — should be skipped"},
    ],
    "reasoning": "Mixed valid/malformed.",
}


class TestMediatorAutoSelect:
    def test_auto_select_calls_selection_and_gap_check(self, sample_problem):
        """Auto-select makes 2 pre-pass analyze calls + 2 run_ptc_round calls + 1 synthesis."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_RESPONSE,
            SAMPLE_GAP_CHECK_NO_GAPS,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        assert client.analyze.call_count == 3   # selection + gap check + synthesis
        assert client.run_ptc_round.call_count == 2  # R1 + R2
        assert isinstance(result, FinalAnalysis)
        assert result.selection_metadata is not None
        assert result.selection_metadata.auto_selected is True

    def test_auto_select_with_weight_zero_deactivates(self, sample_problem):
        """Weight=0 vetoes an auto-selected agent."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_RESPONSE,
            SAMPLE_GAP_CHECK_NO_GAPS,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, weights={"unit_economics": 0}, auto_select=True)
        result = mediator.analyze(sample_problem)

        assert client.analyze.call_count == 3
        assert client.run_ptc_round.call_count == 2
        agent_names = {o.agent_name for o in result.agent_outputs}
        assert "unit_economics" not in agent_names

    def test_auto_select_no_gaps(self, sample_problem):
        """Gap check returns empty, no ad-hoc agents created."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_RESPONSE,
            SAMPLE_GAP_CHECK_NO_GAPS,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        assert result.selection_metadata.ad_hoc_agents == []

    def test_auto_select_caps_adhoc_at_3(self, sample_problem):
        """LLM returns 5 ad-hoc, only 3 are used."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_RESPONSE,
            SAMPLE_GAP_CHECK_5_ADHOC,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        assert len(result.selection_metadata.ad_hoc_agents) == 3

    def test_auto_select_malformed_entries_filtered(self, sample_problem):
        """Malformed agent entries (missing name/prompt) are dropped."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_MALFORMED,
            SAMPLE_GAP_CHECK_NO_GAPS,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        agent_names = {o.agent_name for o in result.agent_outputs}
        assert "market_dynamics" in agent_names
        # Empty-name and no-name entries should not appear
        assert "" not in agent_names

    def test_default_mode_unaffected(self, sample_problem):
        """Without --auto-select, analyze only called for synthesis."""
        client = _make_ptc_client()

        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)

        assert client.run_ptc_round.call_count == 2
        assert client.analyze.call_count == 1
        assert result.selection_metadata is None

    def test_selection_metadata_in_final_analysis(self, sample_problem):
        """Metadata is populated correctly in the result."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [
            SAMPLE_GENERATION_RESPONSE,
            SAMPLE_GAP_CHECK_WITH_ADHOC,
            SAMPLE_SYNTHESIS_RESPONSE,
        ]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        meta = result.selection_metadata
        assert meta is not None
        assert meta.auto_selected is True
        assert "market_dynamics" in meta.selected_agents
        assert meta.selection_reasoning == "These three cover demand, technical, and financial dimensions."
        assert meta.gap_check_reasoning == "Missing cultural perspective."
        assert len(meta.ad_hoc_agents) == 1
        assert meta.ad_hoc_agents[0].name == "cultural"

    def test_auto_select_fallback_on_failure(self, sample_problem):
        """If selection LLM call fails, fall back to 3 default agents."""
        client = MagicMock(spec=ClaudeClient)
        client.token_usage.return_value = TokenUsage()
        client.analyze.side_effect = [Exception("API error"), SAMPLE_SYNTHESIS_RESPONSE]
        client.run_ptc_round.side_effect = _fake_ptc_round

        mediator = Mediator(client, auto_select=True)
        result = mediator.analyze(sample_problem)

        # 1 failed selection + 1 synthesis = 2 analyze calls
        assert client.analyze.call_count == 2
        assert len(result.agent_outputs) == 12
        assert result.selection_metadata is None


class TestMediatorUserContext:
    def test_no_context_passes_problem_unchanged(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client)
        assert mediator._augmented_problem(sample_problem) == sample_problem

    def test_context_prepended_to_problem(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client, user_context="Bootstrapped SaaS, 2 founders, $8k MRR")
        aug = mediator._augmented_problem(sample_problem)
        assert "User context and constraints:" in aug
        assert "Bootstrapped SaaS" in aug
        assert sample_problem in aug
        assert aug.index("User context") < aug.index(sample_problem)

    def test_context_stored_in_result(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client, user_context="Solo founder, pre-revenue")
        result = mediator.analyze(sample_problem)
        assert result.user_context == "Solo founder, pre-revenue"

    def test_no_context_empty_string_in_result(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client)
        result = mediator.analyze(sample_problem)
        assert result.user_context == ""

    def test_context_passed_to_ptc_round(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client, user_context="VC-backed, Series A")
        mediator.analyze(sample_problem)
        call_args = client.run_ptc_round.call_args_list[0]
        passed_problem = call_args[0][0]
        assert "VC-backed" in passed_problem
        assert sample_problem in passed_problem

    def test_whitespace_only_context_ignored(self, sample_problem):
        client = _make_ptc_client()
        mediator = Mediator(client, user_context="   ")
        assert mediator.user_context == ""
        assert mediator._augmented_problem(sample_problem) == sample_problem
