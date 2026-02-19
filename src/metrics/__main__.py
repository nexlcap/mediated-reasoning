"""Comparison CLI for mediated-reasoning metrics.

Usage:
    python -m src.metrics                          # list all runs with labels
    python -m src.metrics compare "webmcp"         # filter by problem slug substring
    python -m src.metrics compare --label pre-ptc ptc  # filter by specific labels
"""

import argparse
import glob
import json
import math
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Loading & parsing
# ---------------------------------------------------------------------------

def _load_reports(output_dir: str = "output") -> List[Dict]:
    """Load all report.json files under output_dir, return as list of dicts."""
    pattern = os.path.join(output_dir, "**", "report.json")
    reports = []
    for path in glob.glob(pattern, recursive=True):
        try:
            with open(path) as f:
                data = json.load(f)
            data["_path"] = path
            reports.append(data)
        except Exception as e:
            print(f"Warning: could not load {path}: {e}", file=sys.stderr)
    return reports


def _extract_metrics(report: Dict) -> Dict[str, Optional[float]]:
    """Extract all numeric metrics from a report dict."""
    m: Dict[str, Optional[float]] = {}

    # Token usage
    tu = report.get("token_usage") or {}
    m["analyze_input_tok"] = float(tu.get("analyze_input", 0))
    m["analyze_output_tok"] = float(tu.get("analyze_output", 0))
    m["ptc_orch_input_tok"] = float(tu.get("ptc_orchestrator_input", 0))
    m["ptc_orch_output_tok"] = float(tu.get("ptc_orchestrator_output", 0))
    m["total_input_tok"] = float(tu.get("total_input", 0))
    m["total_output_tok"] = float(tu.get("total_output", 0))

    # Timing
    ti = report.get("timing") or {}
    m["round1_s"] = float(ti.get("round1_s", 0))
    m["round2_s"] = float(ti.get("round2_s", 0))
    m["round3_s"] = float(ti.get("round3_s", 0))
    m["total_s"] = float(ti.get("total_s", 0))

    # Module completion
    m["modules_attempted"] = float(report.get("modules_attempted", 0))
    m["modules_completed"] = float(report.get("modules_completed", 0))

    # Source metrics
    sources_claimed = float(report.get("sources_claimed", 0))
    sources_survived = float(len(report.get("sources") or []))
    m["sources_claimed"] = sources_claimed
    m["sources_survived"] = sources_survived
    if sources_claimed > 0:
        m["source_survival_pct"] = round(100.0 * sources_survived / sources_claimed, 1)
    else:
        m["source_survival_pct"] = None

    # Priority flags
    flags = report.get("priority_flags") or []
    m["flags_red"] = float(sum(1 for f in flags if str(f).lower().startswith("red:")))
    m["flags_yellow"] = float(sum(1 for f in flags if str(f).lower().startswith("yellow:")))
    m["flags_green"] = float(sum(1 for f in flags if str(f).lower().startswith("green:")))

    # Conflicts
    conflicts = report.get("conflicts") or []
    m["conflicts_total"] = float(len(conflicts))

    # Layer 3 audit
    audit = report.get("audit") or {}
    l3_total = audit.get("layer3_total", 0)
    l3_ok = audit.get("layer3_ok", 0)
    if l3_total and l3_total > 0:
        m["l3_ok_pct"] = round(100.0 * l3_ok / l3_total, 1)
    else:
        m["l3_ok_pct"] = None

    return m


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _stats(values: List[float]) -> Tuple[float, float]:
    """Return (mean, std) for a list of floats. std=0 for single values."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

_PCT_METRICS = {"source_survival_pct", "l3_ok_pct"}
_TIME_METRICS = {"round1_s", "round2_s", "round3_s", "total_s"}
_TOKEN_METRICS = {
    "analyze_input_tok", "analyze_output_tok",
    "ptc_orch_input_tok", "ptc_orch_output_tok",
    "total_input_tok", "total_output_tok",
}


def _fmt_val(key: str, mean: float, std: float, n: int) -> str:
    if key in _PCT_METRICS:
        s = f"{mean:.0f}%"
        if n > 1 and std > 0:
            s += f" ± {std:.0f}%"
    elif key in _TIME_METRICS:
        s = f"{mean:.1f}s"
        if n > 1 and std > 0:
            s += f" ± {std:.1f}s"
    elif key in _TOKEN_METRICS:
        s = f"{mean:,.0f}"
        if n > 1 and std > 0:
            s += f" ± {std:,.0f}"
    else:
        s = f"{mean:.1f}"
        if n > 1 and std > 0:
            s += f" ± {std:.1f}"
    return s


def _fmt_delta(key: str, base_mean: float, cmp_mean: float) -> str:
    if base_mean == 0:
        return "NEW" if cmp_mean != 0 else "="
    pct = 100.0 * (cmp_mean - base_mean) / base_mean
    if abs(pct) < 0.5:
        return "="
    sign = "+" if pct > 0 else ""
    marker = ""
    # Highlight large timing improvements
    if key in _TIME_METRICS and pct < -20:
        marker = "  ←"
    return f"{sign}{pct:.1f}%{marker}"


# ---------------------------------------------------------------------------
# List command
# ---------------------------------------------------------------------------

def cmd_list(reports: List[Dict]) -> None:
    if not reports:
        print("No report.json files found under output/")
        return

    print(f"{'Label':<20} {'Problem':<50} {'Path'}")
    print("─" * 100)
    for r in reports:
        label = r.get("run_label") or "(none)"
        problem = (r.get("problem") or "")[:48]
        path = r.get("_path", "")
        print(f"{label:<20} {problem:<50} {path}")


# ---------------------------------------------------------------------------
# Compare command
# ---------------------------------------------------------------------------

def cmd_compare(
    reports: List[Dict],
    problem_slug: Optional[str] = None,
    labels: Optional[List[str]] = None,
) -> None:
    # Filter by problem slug
    if problem_slug:
        reports = [r for r in reports if problem_slug.lower() in (r.get("problem") or "").lower()]

    # Filter by labels
    if labels:
        reports = [r for r in reports if (r.get("run_label") or "") in labels]

    if not reports:
        print("No matching reports found.")
        return

    # Group by run_label
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for r in reports:
        label = r.get("run_label") or "(none)"
        groups[label].append(r)

    label_list = sorted(groups.keys())

    # Extract metrics per group
    group_metrics: Dict[str, List[Dict[str, Optional[float]]]] = {}
    for label in label_list:
        group_metrics[label] = [_extract_metrics(r) for r in groups[label]]

    # All metric keys (preserve order)
    all_keys = list(_extract_metrics({}))  # call with empty dict to get key list

    # Header
    n_runs = sum(len(v) for v in groups.values())
    slug_desc = f" — problem contains '{problem_slug}'" if problem_slug else ""
    print(f"\nRuns: {n_runs} across {len(label_list)} label(s){slug_desc}\n")

    col_w = 22
    key_w = 28
    header = f"{'Metric':<{key_w}}"
    for label in label_list:
        n = len(groups[label])
        header += f"  {label} (n={n})".ljust(col_w)
    if len(label_list) == 2:
        header += "  Δ"
    print(header)
    print("─" * (key_w + col_w * len(label_list) + 10))

    # Separators between metric groups
    _SEPARATORS = {
        "round1_s": True,
        "modules_attempted": True,
        "sources_claimed": True,
        "flags_red": True,
        "l3_ok_pct": True,
    }

    for key in all_keys:
        if _SEPARATORS.get(key):
            print("─" * (key_w + col_w * len(label_list) + 10))

        row = f"{key:<{key_w}}"
        col_means = []
        for label in label_list:
            values = [
                m[key] for m in group_metrics[label] if m.get(key) is not None
            ]
            n = len(values)
            if n == 0:
                row += "  " + "—".ljust(col_w - 2)
                col_means.append(None)
            else:
                mean, std = _stats(values)
                col_means.append(mean)
                row += "  " + _fmt_val(key, mean, std, n).ljust(col_w - 2)

        if len(label_list) == 2 and col_means[0] is not None and col_means[1] is not None:
            row += "  " + _fmt_delta(key, col_means[0], col_means[1])
        elif len(label_list) == 2 and col_means[1] is not None and col_means[0] is None:
            row += "  NEW"

        print(row)

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare metrics across mediated-reasoning runs"
    )
    subparsers = parser.add_subparsers(dest="command")

    # 'compare' subcommand
    cmp_parser = subparsers.add_parser("compare", help="Compare runs by problem slug or label")
    cmp_parser.add_argument("slug", nargs="?", default=None, help="Filter by problem substring")
    cmp_parser.add_argument("--label", nargs="+", default=None, help="Filter by run labels")
    cmp_parser.add_argument("--output-dir", default="output", help="Directory containing run outputs")

    # 'list' subcommand (default when no subcommand)
    list_parser = subparsers.add_parser("list", help="List all runs with their labels")
    list_parser.add_argument("--output-dir", default="output", help="Directory containing run outputs")

    args = parser.parse_args()

    # Default to 'list' when no subcommand given
    if args.command is None:
        output_dir = "output"
        reports = _load_reports(output_dir)
        cmd_list(reports)
        return

    output_dir = args.output_dir
    reports = _load_reports(output_dir)

    if args.command == "list":
        cmd_list(reports)
    elif args.command == "compare":
        cmd_compare(reports, problem_slug=args.slug, labels=args.label)


if __name__ == "__main__":
    main()
