import pytest
from pydantic import ValidationError

from src.models.schemas import AdHocModule, Conflict, FinalAnalysis, ModuleOutput, SelectionMetadata


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


class TestConflict:
    def test_basic_construction(self):
        c = Conflict(
            modules=["market", "cost"],
            topic="burn rate",
            description="High burn rate risk",
            severity="high",
        )
        assert c.modules == ["market", "cost"]
        assert c.topic == "burn rate"
        assert c.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Conflict(
                modules=["market"],
                topic="test",
                description="test",
                severity="extreme",
            )


class TestFinalAnalysis:
    def test_basic_construction(self):
        conflict = Conflict(
            modules=["market", "cost"],
            topic="burn rate",
            description="conflict 1",
            severity="high",
        )
        analysis = FinalAnalysis(
            problem="test problem",
            conflicts=[conflict],
            synthesis="synthesis text",
            recommendations=["rec 1"],
            priority_flags=["red: critical"],
        )
        assert analysis.problem == "test problem"
        assert len(analysis.conflicts) == 1
        assert analysis.conflicts[0].topic == "burn rate"

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


class TestSelectionMetadata:
    def test_defaults(self):
        meta = SelectionMetadata()
        assert meta.auto_selected is False
        assert meta.selected_modules == []
        assert meta.selection_reasoning == ""
        assert meta.gap_check_reasoning == ""
        assert meta.ad_hoc_modules == []

    def test_with_ad_hoc_modules(self):
        adhoc = AdHocModule(name="cultural", system_prompt="You are a cultural expert.")
        meta = SelectionMetadata(
            auto_selected=True,
            selected_modules=["market", "tech"],
            selection_reasoning="Core modules",
            gap_check_reasoning="Cultural gap found",
            ad_hoc_modules=[adhoc],
        )
        assert meta.auto_selected is True
        assert len(meta.ad_hoc_modules) == 1
        assert meta.ad_hoc_modules[0].name == "cultural"


class TestAdHocModule:
    def test_basic_construction(self):
        m = AdHocModule(name="custom", system_prompt="You are a custom expert.")
        assert m.name == "custom"
        assert "custom expert" in m.system_prompt


class TestFinalAnalysisSelectionMetadata:
    def test_default_none(self):
        analysis = FinalAnalysis(problem="test")
        assert analysis.selection_metadata is None

    def test_with_metadata(self):
        meta = SelectionMetadata(
            auto_selected=True,
            selected_modules=["market", "tech"],
            selection_reasoning="Relevant modules",
        )
        analysis = FinalAnalysis(problem="test", selection_metadata=meta)
        assert analysis.selection_metadata is not None
        assert analysis.selection_metadata.auto_selected is True
        assert "market" in analysis.selection_metadata.selected_modules
