from src.models.schemas import FinalAnalysis, ModuleOutput
from src.utils.formatters import (
    BOLD, RESET, RED, YELLOW, GREEN,
    _colorize_flag,
    format_detailed_report,
)


def _make_analysis():
    return FinalAnalysis(
        problem="Test a mobile app idea",
        module_outputs=[
            ModuleOutput(
                module_name="market",
                round=1,
                analysis={"summary": "Large TAM", "key_findings": "Growing segment"},
                flags=["green: viable market"],
            ),
            ModuleOutput(
                module_name="technical",
                round=1,
                analysis={"summary": "Feasible stack", "risks": "Scaling concerns"},
                flags=["yellow: moderate complexity"],
            ),
            ModuleOutput(
                module_name="market",
                round=2,
                analysis={"summary": "Revised TAM after feedback", "opportunities": "Adjacent markets"},
                flags=["green: confirmed viable"],
                revised=True,
            ),
            ModuleOutput(
                module_name="technical",
                round=2,
                analysis={"summary": "Revised feasibility", "risks": "Reduced after review"},
                flags=["green: feasible"],
                revised=True,
            ),
        ],
        conflicts=["Market optimism vs technical caution on timeline"],
        synthesis="The idea is viable with caveats.",
        recommendations=["Start with MVP", "Validate with users early"],
        priority_flags=["red: high burn rate risk", "green: strong market fit"],
    )


class TestColorizeFlag:
    def test_red_flag(self):
        result = _colorize_flag("red: danger")
        assert result == f"{RED}red: danger{RESET}"

    def test_yellow_flag(self):
        result = _colorize_flag("yellow: caution")
        assert result == f"{YELLOW}yellow: caution{RESET}"

    def test_green_flag(self):
        result = _colorize_flag("green: go")
        assert result == f"{GREEN}green: go{RESET}"

    def test_unknown_flag(self):
        result = _colorize_flag("blue: unknown")
        assert result == "blue: unknown"

    def test_case_insensitive(self):
        result = _colorize_flag("Red: ALERT")
        assert result == f"{RED}Red: ALERT{RESET}"


class TestFormatDetailedReport:
    def test_contains_all_sections(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "DETAILED ANALYSIS REPORT" in report
        assert "Section 1: Executive Summary" in report
        assert "Section 2: Round 1" in report
        assert "Section 3: Round 2" in report
        assert "Section 4: Conflicts" in report
        assert "Section 5: Recommendations" in report

    def test_contains_module_names(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "MARKET" in report
        assert "TECHNICAL" in report

    def test_contains_round1_content(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "Large TAM" in report
        assert "Feasible stack" in report

    def test_contains_round2_content(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "Revised TAM after feedback" in report
        assert "Revised feasibility" in report

    def test_contains_conflicts(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "Market optimism vs technical caution on timeline" in report

    def test_contains_recommendations(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "1. Start with MVP" in report
        assert "2. Validate with users early" in report

    def test_contains_synthesis(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "The idea is viable with caveats." in report

    def test_empty_analysis(self):
        analysis = FinalAnalysis(problem="Empty test")
        report = format_detailed_report(analysis)
        assert "DETAILED ANALYSIS REPORT" in report
        assert "No Round 1 outputs recorded." in report
        assert "No Round 2 outputs recorded." in report
        assert "No conflicts identified." in report
        assert "No recommendations provided." in report
