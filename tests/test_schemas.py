import pytest
from pydantic import ValidationError

from src.models.schemas import ModuleOutput, FinalAnalysis


class TestModuleOutput:
    def test_basic_construction(self):
        output = ModuleOutput(
            module_name="market",
            round=1,
            analysis={"summary": "test"},
            flags=["green: ok"],
        )
        assert output.module_name == "market"
        assert output.round == 1
        assert output.revised is False

    def test_defaults(self):
        output = ModuleOutput(module_name="tech", round=2)
        assert output.analysis == {}
        assert output.flags == []
        assert output.revised is False

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            ModuleOutput()

    def test_revised_flag(self):
        output = ModuleOutput(module_name="cost", round=2, revised=True)
        assert output.revised is True


class TestFinalAnalysis:
    def test_basic_construction(self):
        analysis = FinalAnalysis(
            problem="test problem",
            conflicts=["conflict 1"],
            synthesis="synthesis text",
            recommendations=["rec 1"],
            priority_flags=["red: critical"],
        )
        assert analysis.problem == "test problem"
        assert len(analysis.conflicts) == 1

    def test_defaults(self):
        analysis = FinalAnalysis(problem="test")
        assert analysis.module_outputs == []
        assert analysis.conflicts == []
        assert analysis.synthesis == ""
        assert analysis.recommendations == []
        assert analysis.priority_flags == []

    def test_missing_problem(self):
        with pytest.raises(ValidationError):
            FinalAnalysis()

    def test_with_module_outputs(self):
        output = ModuleOutput(module_name="legal", round=1)
        analysis = FinalAnalysis(problem="test", module_outputs=[output])
        assert len(analysis.module_outputs) == 1
        assert analysis.module_outputs[0].module_name == "legal"
