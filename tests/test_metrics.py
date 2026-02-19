"""Tests for src/metrics comparison CLI."""
import io
import math
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from src.metrics.__main__ import (
    _extract_metrics,
    _fmt_delta,
    _fmt_val,
    _load_reports,
    _stats,
    cmd_compare,
    cmd_list,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_report(
    problem="test problem",
    run_label="pre-ptc",
    total_input=40000,
    total_output=8000,
    round1_s=12.0,
    round2_s=48.0,
    round3_s=8.0,
    modules_attempted=3,
    modules_completed=3,
    sources_claimed=20,
    sources_survived=15,
    flags=None,
    conflicts=None,
    audit=None,
):
    if flags is None:
        flags = ["red: risk A", "yellow: caution B", "green: ok"]
    if conflicts is None:
        conflicts = [{"modules": ["market", "tech"], "topic": "t", "description": "d", "severity": "high"}]
    total_s = round1_s + round2_s + round3_s
    return {
        "problem": problem,
        "run_label": run_label,
        "token_usage": {
            "analyze_input": total_input - 1000,
            "analyze_output": total_output - 500,
            "chat_input": 0,
            "chat_output": 0,
            "ptc_orchestrator_input": 1000,
            "ptc_orchestrator_output": 500,
            "total_input": total_input,
            "total_output": total_output,
        },
        "timing": {
            "round1_s": round1_s,
            "round2_s": round2_s,
            "round3_s": round3_s,
            "total_s": total_s,
        },
        "modules_attempted": modules_attempted,
        "modules_completed": modules_completed,
        "sources_claimed": sources_claimed,
        "sources": [f"source {i}" for i in range(sources_survived)],
        "priority_flags": flags,
        "conflicts": conflicts,
        "audit": audit or {"layer3_total": 10, "layer3_ok": 8},
    }


# ---------------------------------------------------------------------------
# _extract_metrics
# ---------------------------------------------------------------------------

class TestExtractMetrics:
    def test_token_fields(self):
        r = _make_report(total_input=50000, total_output=9000)
        m = _extract_metrics(r)
        assert m["total_input_tok"] == 50000.0
        assert m["total_output_tok"] == 9000.0

    def test_timing_fields(self):
        r = _make_report(round1_s=10.0, round2_s=45.0, round3_s=5.0)
        m = _extract_metrics(r)
        assert m["round1_s"] == 10.0
        assert m["round2_s"] == 45.0
        assert m["total_s"] == 60.0

    def test_source_survival(self):
        r = _make_report(sources_claimed=20, sources_survived=15)
        m = _extract_metrics(r)
        assert m["sources_claimed"] == 20.0
        assert m["sources_survived"] == 15.0
        assert m["source_survival_pct"] == 75.0

    def test_source_survival_pct_none_when_zero_claimed(self):
        r = _make_report(sources_claimed=0, sources_survived=0)
        m = _extract_metrics(r)
        assert m["source_survival_pct"] is None

    def test_flag_counts(self):
        r = _make_report(flags=["red: A", "red: B", "yellow: C", "green: D"])
        m = _extract_metrics(r)
        assert m["flags_red"] == 2.0
        assert m["flags_yellow"] == 1.0
        assert m["flags_green"] == 1.0

    def test_conflict_count(self):
        r = _make_report(conflicts=[{}, {}, {}])
        m = _extract_metrics(r)
        assert m["conflicts_total"] == 3.0

    def test_l3_ok_pct(self):
        r = _make_report(audit={"layer3_total": 10, "layer3_ok": 9})
        m = _extract_metrics(r)
        assert m["l3_ok_pct"] == 90.0

    def test_l3_ok_pct_none_when_no_audit(self):
        r = _make_report(audit={"layer3_total": 0, "layer3_ok": 0})
        m = _extract_metrics(r)
        assert m["l3_ok_pct"] is None

    def test_empty_report(self):
        """Empty report with no optional fields should not raise."""
        m = _extract_metrics({})
        assert m["total_input_tok"] == 0.0
        assert m["source_survival_pct"] is None
        assert m["l3_ok_pct"] is None


# ---------------------------------------------------------------------------
# _stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_single_value(self):
        mean, std = _stats([42.0])
        assert mean == 42.0
        assert std == 0.0

    def test_multiple_values(self):
        mean, std = _stats([10.0, 20.0, 30.0])
        assert mean == 20.0
        assert std == pytest.approx(10.0, abs=0.01)

    def test_empty(self):
        mean, std = _stats([])
        assert mean == 0.0
        assert std == 0.0


# ---------------------------------------------------------------------------
# _fmt_val / _fmt_delta
# ---------------------------------------------------------------------------

class TestFormatters:
    def test_fmt_val_token(self):
        s = _fmt_val("total_input_tok", 45234.0, 812.0, 3)
        assert "45,234" in s
        assert "812" in s

    def test_fmt_val_time(self):
        s = _fmt_val("round2_s", 48.2, 3.1, 3)
        assert "48.2s" in s
        assert "3.1s" in s

    def test_fmt_val_pct(self):
        s = _fmt_val("source_survival_pct", 74.0, 4.0, 3)
        assert "74%" in s

    def test_fmt_delta_positive(self):
        d = _fmt_delta("total_input_tok", 45000.0, 47000.0)
        assert d.startswith("+")
        assert "4.4%" in d

    def test_fmt_delta_negative(self):
        d = _fmt_delta("round2_s", 48.0, 12.0)
        assert d.startswith("-")
        assert "←" in d  # large timing improvement gets marker

    def test_fmt_delta_equal(self):
        d = _fmt_delta("modules_attempted", 3.0, 3.0)
        assert d == "="

    def test_fmt_delta_new(self):
        d = _fmt_delta("ptc_orch_input_tok", 0.0, 1240.0)
        assert d == "NEW"

    def test_fmt_delta_base_zero_cmp_zero(self):
        d = _fmt_delta("ptc_orch_input_tok", 0.0, 0.0)
        assert d == "="


# ---------------------------------------------------------------------------
# _load_reports
# ---------------------------------------------------------------------------

class TestLoadReports:
    def test_loads_json_files(self, tmp_path):
        run_dir = tmp_path / "run1"
        run_dir.mkdir()
        report = _make_report(run_label="pre-ptc")
        (run_dir / "report.json").write_text(json.dumps(report))

        reports = _load_reports(str(tmp_path))
        assert len(reports) == 1
        assert reports[0]["run_label"] == "pre-ptc"
        assert "_path" in reports[0]

    def test_loads_nested(self, tmp_path):
        for i in range(3):
            d = tmp_path / f"run{i}"
            d.mkdir()
            (d / "report.json").write_text(json.dumps(_make_report(run_label=f"label{i}")))

        reports = _load_reports(str(tmp_path))
        assert len(reports) == 3

    def test_skips_invalid_json(self, tmp_path, capsys):
        d = tmp_path / "bad"
        d.mkdir()
        (d / "report.json").write_text("not valid json {{{")

        reports = _load_reports(str(tmp_path))
        assert reports == []
        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_empty_dir(self, tmp_path):
        reports = _load_reports(str(tmp_path))
        assert reports == []


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

class TestCmdList:
    def test_prints_label_and_problem(self, capsys):
        reports = [_make_report(problem="my test problem", run_label="pre-ptc")]
        cmd_list(reports)
        captured = capsys.readouterr()
        assert "pre-ptc" in captured.out
        assert "my test problem" in captured.out

    def test_empty_reports(self, capsys):
        cmd_list([])
        captured = capsys.readouterr()
        assert "No report" in captured.out


# ---------------------------------------------------------------------------
# cmd_compare
# ---------------------------------------------------------------------------

class TestCmdCompare:
    def _two_label_reports(self, n=2):
        reports = []
        for _ in range(n):
            reports.append(_make_report(
                problem="WebMCP browser standard",
                run_label="pre-ptc",
                round2_s=48.0,
                total_input=45000,
            ))
        for _ in range(n):
            reports.append(_make_report(
                problem="WebMCP browser standard",
                run_label="ptc",
                round2_s=12.0,
                total_input=46000,
            ))
        return reports

    def test_compare_shows_both_labels(self, capsys):
        reports = self._two_label_reports()
        cmd_compare(reports)
        out = capsys.readouterr().out
        assert "pre-ptc" in out
        assert "ptc" in out

    def test_compare_slug_filter(self, capsys):
        reports = self._two_label_reports()
        # Add an unrelated report
        reports.append(_make_report(problem="unrelated topic", run_label="other"))
        cmd_compare(reports, problem_slug="webmcp")
        out = capsys.readouterr().out
        assert "other" not in out
        assert "pre-ptc" in out

    def test_compare_label_filter(self, capsys):
        reports = self._two_label_reports()
        cmd_compare(reports, labels=["ptc"])
        out = capsys.readouterr().out
        assert "ptc" in out
        # pre-ptc should be absent from the comparison table (filtered out)
        lines = [l for l in out.splitlines() if "pre-ptc" in l]
        assert len(lines) == 0

    def test_compare_delta_column(self, capsys):
        reports = self._two_label_reports(n=3)
        cmd_compare(reports)
        out = capsys.readouterr().out
        # Delta column should appear for 2-label comparison
        assert "←" in out  # round2_s drops by >20%

    def test_compare_no_matching_reports(self, capsys):
        reports = self._two_label_reports()
        cmd_compare(reports, problem_slug="nonexistent_slug_xyz")
        out = capsys.readouterr().out
        assert "No matching" in out

    def test_compare_single_label(self, capsys):
        """Single label: no delta column, no crash."""
        reports = [_make_report(run_label="solo") for _ in range(2)]
        cmd_compare(reports)
        out = capsys.readouterr().out
        assert "solo" in out

    def test_compare_missing_metrics_handled(self, capsys):
        """Reports missing token_usage/timing should not crash."""
        reports = [
            {"problem": "test", "run_label": "bare", "sources": [], "priority_flags": [], "conflicts": []},
            {"problem": "test", "run_label": "bare", "sources": [], "priority_flags": [], "conflicts": []},
        ]
        cmd_compare(reports)
        out = capsys.readouterr().out
        assert "bare" in out
