import pytest

from src.modules import MODULE_REGISTRY
from src.modules.market_module import MarketModule
from src.modules.cost_module import CostModule
from src.modules.risk_module import RiskModule


class TestModuleRegistry:
    def test_registry_has_three_modules(self):
        assert len(MODULE_REGISTRY) == 3

    def test_registry_contains_all_modules(self):
        classes = set(MODULE_REGISTRY)
        assert MarketModule in classes
        assert CostModule in classes
        assert RiskModule in classes


class TestModuleRound1:
    @pytest.mark.parametrize(
        "module_cls,expected_name",
        [
            (MarketModule, "market"),
            (CostModule, "cost"),
            (RiskModule, "risk"),
        ],
    )
    def test_round1_produces_valid_output(
        self, mock_client, sample_problem, module_cls, expected_name
    ):
        module = module_cls(mock_client)
        assert module.name == expected_name

        output = module.run_round1(sample_problem)
        assert output.module_name == expected_name
        assert output.round == 1
        assert output.revised is False
        assert isinstance(output.analysis, dict)
        assert isinstance(output.flags, list)
        mock_client.analyze.assert_called_once()


class TestModuleRound2:
    def test_round2_produces_revised_output(self, mock_client, sample_problem):
        module = MarketModule(mock_client)
        round1_outputs = [
            {
                "module_name": "tech",
                "round": 1,
                "analysis": {"summary": "tech analysis"},
                "flags": [],
                "revised": False,
            }
        ]
        output = module.run_round2(sample_problem, round1_outputs)
        assert output.module_name == "market"
        assert output.round == 2
        assert output.revised is True
