import pytest
from pydantic import ValidationError

from src.models.schemas import AdHocAgent, Conflict, FinalAnalysis, AgentOutput, SelectionMetadata


class TestAgentOutput:
    def test_basic_construction(self):
        output = AgentOutput(
            agent_name="market",
            round=1,
            analysis={"summary": "test"},
            flags=["green: ok"],
        )
        assert output.agent_name == "market"
        assert output.round == 1
        assert output.revised is False

    def test_defaults(self):
        output = AgentOutput(agent_name="tech", round=2)
        assert output.analysis == {}
        assert output.flags == []
        assert output.revised is False

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            AgentOutput()

    def test_revised_flag(self):
        output = AgentOutput(agent_name="cost", round=2, revised=True)
        assert output.revised is True


class TestConflict:
    def test_basic_construction(self):
        c = Conflict(
            agents=["market", "cost"],
            topic="burn rate",
            description="High burn rate risk",
            severity="high",
        )
        assert c.agents == ["market", "cost"]
        assert c.topic == "burn rate"
        assert c.severity == "high"

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Conflict(
                agents=["market"],
                topic="test",
                description="test",
                severity="extreme",
            )


class TestFinalAnalysis:
    def test_basic_construction(self):
        conflict = Conflict(
            agents=["market", "cost"],
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
        assert analysis.agent_outputs == []
        assert analysis.conflicts == []
        assert analysis.synthesis == ""
        assert analysis.recommendations == []
        assert analysis.priority_flags == []

    def test_missing_problem(self):
        with pytest.raises(ValidationError):
            FinalAnalysis()

    def test_with_agent_outputs(self):
        output = AgentOutput(agent_name="legal", round=1)
        analysis = FinalAnalysis(problem="test", agent_outputs=[output])
        assert len(analysis.agent_outputs) == 1
        assert analysis.agent_outputs[0].agent_name == "legal"


class TestSelectionMetadata:
    def test_defaults(self):
        meta = SelectionMetadata()
        assert meta.auto_selected is False
        assert meta.selected_agents == []
        assert meta.selection_reasoning == ""
        assert meta.gap_check_reasoning == ""
        assert meta.ad_hoc_agents == []

    def test_with_ad_hoc_agents(self):
        adhoc = AdHocAgent(name="cultural", system_prompt="You are a cultural expert.")
        meta = SelectionMetadata(
            auto_selected=True,
            selected_agents=["market", "tech"],
            selection_reasoning="Core agents",
            gap_check_reasoning="Cultural gap found",
            ad_hoc_agents=[adhoc],
        )
        assert meta.auto_selected is True
        assert len(meta.ad_hoc_agents) == 1
        assert meta.ad_hoc_agents[0].name == "cultural"


class TestAdHocAgent:
    def test_basic_construction(self):
        m = AdHocAgent(name="custom", system_prompt="You are a custom expert.")
        assert m.name == "custom"
        assert "custom expert" in m.system_prompt


class TestFinalAnalysisSelectionMetadata:
    def test_default_none(self):
        analysis = FinalAnalysis(problem="test")
        assert analysis.selection_metadata is None

    def test_with_metadata(self):
        meta = SelectionMetadata(
            auto_selected=True,
            selected_agents=["market", "tech"],
            selection_reasoning="Relevant agents",
        )
        analysis = FinalAnalysis(problem="test", selection_metadata=meta)
        assert analysis.selection_metadata is not None
        assert analysis.selection_metadata.auto_selected is True
        assert "market" in analysis.selection_metadata.selected_agents
