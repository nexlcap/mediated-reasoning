"""
Tests for the automated hallucination audit (Layers 1 & 2).

These run fast (no network, no LLM) and are executed by the pre-commit hook.
"""
import pytest

from src.audit.prompt_linter import lint
from src.audit.output_validator import validate
from src.models.schemas import (
    Conflict,
    ConflictResolution,
    FinalAnalysis,
    ModuleOutput,
)


# ---------------------------------------------------------------------------
# Layer 1 — Prompt Linter
# ---------------------------------------------------------------------------

class TestPromptLinter:
    def test_no_violations_on_current_codebase(self):
        """Regression guard: the live prompt builders must pass all checks."""
        violations = lint()
        assert violations == [], f"Prompt linter violations:\n" + "\n".join(violations)


# ---------------------------------------------------------------------------
# Layer 2 — Output Integrity Validator
# ---------------------------------------------------------------------------

def _make_analysis(**kwargs) -> FinalAnalysis:
    defaults = dict(
        problem="test",
        sources=["Real Source — https://example.com/real"],
        search_enabled=True,
    )
    defaults.update(kwargs)
    return FinalAnalysis(**defaults)


class TestOutputValidatorClean:
    def test_clean_analysis_has_no_violations(self):
        analysis = _make_analysis(
            synthesis="Good finding [1].",
            recommendations=["Do something [1]."],
        )
        assert validate(analysis) == []

    def test_no_citations_no_sources_is_fine(self):
        analysis = _make_analysis(sources=[], synthesis="Plain text, no citations.")
        assert validate(analysis) == []

    def test_no_search_no_citations_is_fine(self):
        analysis = _make_analysis(
            sources=[],
            search_enabled=False,
            synthesis="Plain analysis, no citations.",
        )
        assert validate(analysis) == []


class TestOutputValidatorSourceUrls:
    def test_url_less_source_flagged(self):
        analysis = _make_analysis(
            sources=["McKinsey Report 2024"],  # no URL
        )
        violations = validate(analysis)
        assert any("no URL" in v for v in violations)

    def test_source_with_url_passes(self):
        analysis = _make_analysis(
            sources=["McKinsey Report — https://mckinsey.com/report"],
        )
        violations = validate(analysis)
        assert not any("no URL" in v for v in violations)

    def test_resolution_source_without_url_flagged(self):
        analysis = _make_analysis(
            conflict_resolutions=[
                ConflictResolution(
                    topic="test conflict",
                    modules=["market"],
                    severity="high",
                    verdict="verdict",
                    updated_recommendation="rec",
                    sources=["No URL source"],
                )
            ],
        )
        violations = validate(analysis)
        assert any("Resolution source" in v and "no URL" in v for v in violations)


class TestOutputValidatorOrphanedCitations:
    def test_valid_citation_passes(self):
        analysis = _make_analysis(
            sources=["Source — https://example.com"],
            synthesis="Some claim [1].",
        )
        assert validate(analysis) == []

    def test_orphaned_citation_flagged(self):
        # [2] cited but only one source exists
        analysis = _make_analysis(
            sources=["Source — https://example.com"],
            synthesis="Some claim [2].",
        )
        violations = validate(analysis)
        assert any("Orphaned" in v and "2" in v for v in violations)

    def test_out_of_range_citation_flagged(self):
        analysis = _make_analysis(
            sources=["Source — https://example.com"],
            recommendations=["Do this [99]."],
        )
        violations = validate(analysis)
        assert any("Orphaned" in v and "99" in v for v in violations)

    def test_citation_in_module_output_flagged(self):
        analysis = _make_analysis(
            sources=["Source — https://example.com"],
            module_outputs=[
                ModuleOutput(
                    module_name="market",
                    round=1,
                    analysis={"summary": "Claim [5]"},
                )
            ],
        )
        violations = validate(analysis)
        assert any("Orphaned" in v and "5" in v for v in violations)


class TestOutputValidatorNoSearchCitations:
    def test_citation_in_no_search_run_flagged(self):
        analysis = _make_analysis(
            sources=[],
            search_enabled=False,
            synthesis="Claim [1].",
        )
        violations = validate(analysis)
        assert any("search_enabled=False" in v for v in violations)

    def test_no_citation_in_no_search_run_passes(self):
        analysis = _make_analysis(
            sources=[],
            search_enabled=False,
            synthesis="Plain claim with no citation.",
        )
        assert validate(analysis) == []


class TestOutputValidatorPipelineDropsFabricatedSources:
    """Simulate what the pipeline does: URL-less sources should be dropped
    *before* FinalAnalysis is built, so a properly filtered analysis is clean."""

    def test_after_url_filter_no_violations(self):
        # URL-less entries already stripped by _consolidate_sources
        analysis = _make_analysis(
            sources=[
                "Grounded Source — https://real.example.com/paper",
                "Another — https://other.example.com/doc",
            ],
            synthesis="Finding A [1]. Finding B [2].",
        )
        assert validate(analysis) == []
