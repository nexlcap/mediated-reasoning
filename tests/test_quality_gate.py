"""
Tests for the run quality gate (src/audit/quality_gate.py).

All tests are pure-logic (no network, no LLM) and run in the pre-commit suite.
"""
import pytest

from src.audit.quality_gate import evaluate
from src.models.schemas import FinalAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sources(n: int) -> list[str]:
    """Return n fake but URL-bearing source strings."""
    return [f"Source {i} — https://example.com/{i}" for i in range(1, n + 1)]


def _make(
    *,
    sources_survived: int = 20,
    sources_claimed: int = 20,
    modules_attempted: int = 3,
    modules_completed: int = 3,
    flags: list[str] | None = None,
    search_enabled: bool = True,
) -> FinalAnalysis:
    return FinalAnalysis(
        problem="test",
        sources=_sources(sources_survived),
        sources_claimed=sources_claimed,
        modules_attempted=modules_attempted,
        modules_completed=modules_completed,
        priority_flags=flags or [],
        search_enabled=search_enabled,
    )


# ---------------------------------------------------------------------------
# Tier boundaries
# ---------------------------------------------------------------------------

class TestTierBoundaries:
    def test_perfect_run_is_good(self):
        q = evaluate(_make())
        assert q.tier == "good"
        assert q.score == 1.0
        assert q.warnings == []

    def test_score_08_is_good(self):
        # One moderate source survival deduction (-0.1) leaves 0.9 → good
        q = evaluate(_make(sources_survived=10, sources_claimed=15))  # 67% survival → -0.1
        assert q.tier == "good"
        assert q.score == pytest.approx(0.9)

    def test_score_05_is_degraded(self):
        # survival <50% (-0.3) + <5 sources (-0.2) = -0.5 → 0.5 → degraded
        q = evaluate(_make(sources_survived=2, sources_claimed=10))
        assert q.tier == "degraded"
        assert q.score == pytest.approx(0.5)

    def test_score_below_05_is_poor(self):
        # One module failed (-0.3) + survival <50% (-0.3) + <5 sources (-0.2) = -0.8 → 0.2 → poor
        q = evaluate(_make(
            sources_survived=2,
            sources_claimed=10,
            modules_attempted=3,
            modules_completed=2,
        ))
        assert q.tier == "poor"
        assert q.score == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Module failures
# ---------------------------------------------------------------------------

class TestModuleFailures:
    def test_one_failed_module_deducts_03(self):
        q = evaluate(_make(modules_attempted=3, modules_completed=2))
        assert q.score == pytest.approx(0.7)
        assert any("failed" in w for w in q.warnings)

    def test_two_failed_modules_deducts_06(self):
        q = evaluate(_make(modules_attempted=3, modules_completed=1))
        assert q.score == pytest.approx(0.4)

    def test_no_failures_no_penalty(self):
        q = evaluate(_make(modules_attempted=5, modules_completed=5))
        assert q.score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Source survival
# ---------------------------------------------------------------------------

class TestSourceSurvival:
    def test_survival_below_50_pct_deducts_03(self):
        # 4/10 = 40% survival → -0.3; also <5 survived → -0.2
        q = evaluate(_make(sources_survived=4, sources_claimed=10))
        assert q.score == pytest.approx(0.5)
        assert any("Low source survival" in w for w in q.warnings)

    def test_survival_between_50_and_70_deducts_01(self):
        # 6/10 = 60% → -0.1; also ≥5 survived → no grounding penalty
        q = evaluate(_make(sources_survived=6, sources_claimed=10))
        assert q.score == pytest.approx(0.9)
        assert any("Moderate source survival" in w for w in q.warnings)

    def test_survival_above_70_no_penalty(self):
        q = evaluate(_make(sources_survived=8, sources_claimed=10))  # 80%
        assert q.score == pytest.approx(1.0)

    def test_perfect_survival_no_penalty(self):
        q = evaluate(_make(sources_survived=20, sources_claimed=20))
        assert q.score == pytest.approx(1.0)

    def test_zero_claimed_no_division_error(self):
        q = evaluate(_make(sources_survived=0, sources_claimed=0, search_enabled=True))
        # No sources and no claimed → only grounding depth penalty applies
        assert q.score == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Grounding depth (sources_survived < 5)
# ---------------------------------------------------------------------------

class TestGroundingDepth:
    def test_fewer_than_5_sources_deducts_02(self):
        q = evaluate(_make(sources_survived=4, sources_claimed=4))  # 100% survival, but <5
        assert q.score == pytest.approx(0.8)
        assert any("Only 4 source" in w for w in q.warnings)

    def test_exactly_5_sources_no_penalty(self):
        q = evaluate(_make(sources_survived=5, sources_claimed=5))
        assert q.score == pytest.approx(1.0)

    def test_grounding_depth_skipped_when_search_disabled(self):
        q = evaluate(_make(sources_survived=0, sources_claimed=0, search_enabled=False))
        assert q.score == pytest.approx(1.0)
        assert q.warnings == []


# ---------------------------------------------------------------------------
# Critical flag density
# ---------------------------------------------------------------------------

class TestCriticalFlags:
    def test_three_red_flags_no_penalty(self):
        flags = ["red: issue A", "red: issue B", "red: issue C"]
        q = evaluate(_make(flags=flags))
        assert q.score == pytest.approx(1.0)

    def test_four_red_flags_deducts_01(self):
        flags = ["red: A", "red: B", "red: C", "red: D"]
        q = evaluate(_make(flags=flags))
        assert q.score == pytest.approx(0.9)
        assert any("critical flags" in w for w in q.warnings)

    def test_non_red_flags_not_counted(self):
        flags = ["yellow: warn", "green: good", "red: A", "red: B"]
        q = evaluate(_make(flags=flags))
        assert q.score == pytest.approx(1.0)  # only 2 red → no penalty

    def test_red_flag_case_insensitive(self):
        flags = ["RED: A", "Red: B", "red: C", "red: D"]
        q = evaluate(_make(flags=flags))
        assert q.score == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Search disabled
# ---------------------------------------------------------------------------

class TestSearchDisabled:
    def test_no_source_penalties_when_search_disabled(self):
        # Even with 0 sources and 0 claimed, no source penalties if search is off
        q = evaluate(_make(sources_survived=0, sources_claimed=5, search_enabled=False))
        assert q.score == pytest.approx(1.0)
        assert q.warnings == []


# ---------------------------------------------------------------------------
# Score clamping
# ---------------------------------------------------------------------------

class TestScoreClamping:
    def test_score_never_below_zero(self):
        # Maximum possible penalties: 3 failures (-0.9) + survival<50% (-0.3)
        # + <5 sources (-0.2) + ≥4 red flags (-0.1) = -1.5 → clamped to 0.0
        flags = ["red: A", "red: B", "red: C", "red: D"]
        q = evaluate(_make(
            sources_survived=1,
            sources_claimed=10,
            modules_attempted=5,
            modules_completed=2,
            flags=flags,
        ))
        assert q.score >= 0.0
        assert q.tier == "poor"

    def test_score_never_above_one(self):
        q = evaluate(_make())
        assert q.score <= 1.0


# ---------------------------------------------------------------------------
# RunQuality schema
# ---------------------------------------------------------------------------

class TestRunQualitySchema:
    def test_quality_attached_to_final_analysis(self):
        analysis = _make()
        assert analysis.quality is None  # not set until mediator calls evaluate()
        analysis.quality = evaluate(analysis)
        assert analysis.quality is not None
        assert analysis.quality.score == 1.0

    def test_warnings_is_list(self):
        q = evaluate(_make())
        assert isinstance(q.warnings, list)

    def test_tier_values_are_valid(self):
        for kwargs in [
            {},
            {"modules_completed": 1},
            {"sources_survived": 1, "sources_claimed": 10},
        ]:
            q = evaluate(_make(**kwargs))
            assert q.tier in ("good", "degraded", "poor")
