from src.models.schemas import Conflict, FinalAnalysis, ModuleOutput
from src.utils.formatters import (
    BOLD, RESET, RED, YELLOW, GREEN,
    _colorize_flag,
    format_customer_report,
    format_detailed_report,
    format_final_analysis,
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
        conflicts=[
            Conflict(
                modules=["market", "technical"],
                topic="timeline",
                description="Market optimism vs technical caution on timeline",
                severity="medium",
            )
        ],
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
        assert "TL;DR" in report
        assert "Detailed Evidence" in report
        assert "Round 1" in report
        assert "Round 2" in report
        assert "Conflicts" in report
        assert "Recommendations" in report

    def test_contains_transition_text(self):
        analysis = _make_analysis()
        report = format_detailed_report(analysis)
        assert "2 independent analysis modules" in report
        assert "each running 2 rounds" in report

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
        assert "[MEDIUM]" in report
        assert "market vs technical" in report
        assert "timeline" in report
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


class TestFormatCustomerReport:
    def test_contains_expected_sections(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "ANALYSIS REPORT" in report
        assert "Problem:" in report
        assert "Priority Flags:" in report
        assert "Key Findings:" in report
        assert "Recommendations:" in report

    def test_contains_problem(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "Test a mobile app idea" in report

    def test_contains_synthesis(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "The idea is viable with caveats." in report

    def test_contains_recommendations(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "1. Start with MVP" in report
        assert "2. Validate with users early" in report

    def test_contains_priority_flags(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "high burn rate risk" in report
        assert "strong market fit" in report

    def test_omits_module_names(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "MARKET" not in report
        assert "TECHNICAL" not in report

    def test_omits_round_details(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "Round 1" not in report
        assert "Round 2" not in report

    def test_omits_methodology(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "independent analysis modules" not in report
        assert "Detailed Evidence" not in report

    def test_omits_cross_module_sections(self):
        analysis = _make_analysis()
        report = format_customer_report(analysis)
        assert "Cross-Module" not in report
        assert "Conflicts" not in report

    def test_contains_sources(self):
        analysis = _make_analysis()
        analysis.sources = ["Source A", "Source B"]
        report = format_customer_report(analysis)
        assert "[1] Source A" in report
        assert "[2] Source B" in report

    def test_empty_analysis(self):
        analysis = FinalAnalysis(problem="Empty test")
        report = format_customer_report(analysis)
        assert "ANALYSIS REPORT" in report
        assert "Empty test" in report
        assert "Key Findings" not in report
        assert "Recommendations" not in report


class TestDeactivatedDisclaimer:
    DISCLAIMER = "The cost module was deactivated and its analysis is not reflected."

    def _make_analysis_with_disclaimer(self):
        analysis = _make_analysis()
        analysis.deactivated_disclaimer = self.DISCLAIMER
        return analysis

    def test_disclaimer_in_final_analysis(self):
        report = format_final_analysis(self._make_analysis_with_disclaimer())
        assert self.DISCLAIMER in report
        assert "Note:" in report

    def test_disclaimer_in_detailed_report(self):
        report = format_detailed_report(self._make_analysis_with_disclaimer())
        assert self.DISCLAIMER in report
        assert "Note:" in report

    def test_disclaimer_in_customer_report(self):
        report = format_customer_report(self._make_analysis_with_disclaimer())
        assert self.DISCLAIMER in report
        assert "Note:" in report

    def test_no_disclaimer_when_empty(self):
        report = format_final_analysis(_make_analysis())
        assert "Note:" not in report

    def test_no_disclaimer_in_detailed_when_empty(self):
        report = format_detailed_report(_make_analysis())
        assert "Note:" not in report

    def test_no_disclaimer_in_customer_when_empty(self):
        report = format_customer_report(_make_analysis())
        assert "Note:" not in report
