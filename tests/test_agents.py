import pytest

from src.agents import AGENT_REGISTRY
from src.agents.market_agent import MarketAgent
from src.agents.cost_agent import CostAgent
from src.agents.risk_agent import RiskAgent


class TestAgentRegistry:
    def test_registry_has_six_agents(self):
        assert len(AGENT_REGISTRY) == 6

    def test_registry_contains_all_agents(self):
        classes = set(AGENT_REGISTRY)
        assert MarketAgent in classes
        assert CostAgent in classes
        assert RiskAgent in classes


class TestAgentRound1:
    @pytest.mark.parametrize(
        "agent_cls,expected_name",
        [
            (MarketAgent, "market"),
            (CostAgent, "cost"),
            (RiskAgent, "risk"),
        ],
    )
    def test_round1_produces_valid_output(
        self, mock_client, sample_problem, agent_cls, expected_name
    ):
        agent = agent_cls(mock_client)
        assert agent.name == expected_name

        output = agent.run_round1(sample_problem)
        assert output.agent_name == expected_name
        assert output.round == 1
        assert output.revised is False
        assert isinstance(output.analysis, dict)
        assert isinstance(output.flags, list)
        mock_client.analyze.assert_called_once()


class TestAgentRound2:
    def test_round2_produces_revised_output(self, mock_client, sample_problem):
        agent = MarketAgent(mock_client)
        round1_outputs = [
            {
                "agent_name": "tech",
                "round": 1,
                "analysis": {"summary": "tech analysis"},
                "flags": [],
                "revised": False,
            }
        ]
        output = agent.run_round2(sample_problem, round1_outputs)
        assert output.agent_name == "market"
        assert output.round == 2
        assert output.revised is True
