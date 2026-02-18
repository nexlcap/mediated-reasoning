from src.models.schemas import Conflict, ConflictResolution, FinalAnalysis, ModuleOutput


# ANSI color codes
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
BOLD = "\033[1m"
RESET = "\033[0m"
CYAN = "\033[96m"

FLAG_COLORS = {
    "red": RED,
    "yellow": YELLOW,
    "green": GREEN,
}

SEVERITY_COLORS = {
    "high": RED,
    "medium": YELLOW,
}


def _format_conflict(conflict: Conflict) -> str:
    severity_tag = conflict.severity.upper()
    color = SEVERITY_COLORS.get(conflict.severity, "")
    reset = RESET if color else ""
    modules = " vs ".join(conflict.modules)
    return f"  - {color}[{severity_tag}]{reset} {modules} — {conflict.topic}: {conflict.description}"


def _colorize_flag(flag: str) -> str:
    lower = flag.lower()
    for level, color in FLAG_COLORS.items():
        if lower.startswith(level):
            return f"{color}{flag}{RESET}"
    return flag


def _format_module_detail(output: ModuleOutput) -> list[str]:
    lines = [f"{CYAN}{BOLD}[{output.module_name.upper()}]{RESET}"]
    for key, value in output.analysis.items():
        if isinstance(value, list):
            lines.append(f"  {BOLD}{key}:{RESET}")
            for item in value:
                lines.append(f"    - {item}")
        else:
            lines.append(f"  {BOLD}{key}:{RESET} {value}")
    if output.flags:
        flags_str = ", ".join(_colorize_flag(f) for f in output.flags)
        lines.append(f"  {BOLD}Flags:{RESET} {flags_str}")
    if output.sources:
        lines.append(f"  {BOLD}Sources:{RESET}")
        for i, source in enumerate(output.sources, 1):
            lines.append(f"    [{i}] {source}")
    lines.append("")
    return lines


def _format_analysis_config(analysis: FinalAnalysis) -> list[str]:
    """Render the Analysis Configuration block (modules, weights, RACI, search)."""
    lines = [f"{BOLD}Analysis Configuration:{RESET}"]

    # Active modules with weights
    active_modules = list(dict.fromkeys(
        o.module_name for o in analysis.module_outputs
    ))
    if active_modules:
        module_parts = []
        for name in active_modules:
            w = analysis.weights.get(name, 1)
            module_parts.append(f"{name} ({w}x)" if w != 1 else name)
        lines.append(f"  {BOLD}Modules:{RESET} {', '.join(module_parts)}")

    # Deactivated modules
    deactivated = [
        name for name, w in analysis.weights.items()
        if w == 0 and name not in active_modules
    ]
    if deactivated:
        lines.append(f"  {BOLD}Deactivated:{RESET} {', '.join(deactivated)}")

    # Web search
    search_status = "enabled" if analysis.search_enabled else "disabled"
    source_count = len(analysis.sources)
    lines.append(
        f"  {BOLD}Web search:{RESET} {search_status}"
        + (f" ({source_count} sources fetched)" if analysis.search_enabled and source_count else "")
    )

    # Ad-hoc modules (from selection metadata)
    meta = analysis.selection_metadata
    if meta and meta.ad_hoc_modules:
        adhoc_names = ", ".join(m.name for m in meta.ad_hoc_modules)
        lines.append(f"  {BOLD}Ad-hoc modules:{RESET} {adhoc_names}")

    # RACI matrix
    if analysis.raci_matrix:
        lines.append(f"  {BOLD}RACI matrix:{RESET}")
        col_w = [28, 14, 14, 14, 14]
        header = (
            f"    {'Topic':<{col_w[0]}} {'Responsible':<{col_w[1]}} "
            f"{'Accountable':<{col_w[2]}} {'Consulted':<{col_w[3]}} {'Informed':<{col_w[4]}}"
        )
        sep = "    " + "-" * (sum(col_w) + 4 * 1)
        lines.append(sep)
        lines.append(header)
        lines.append(sep)
        for topic, roles in analysis.raci_matrix.items():
            c = ", ".join(roles["C"]) if isinstance(roles.get("C"), list) else (roles.get("C") or "")
            i = ", ".join(roles["I"]) if isinstance(roles.get("I"), list) else (roles.get("I") or "")
            row = (
                f"    {topic:<{col_w[0]}} {roles.get('R', ''):<{col_w[1]}} "
                f"{roles.get('A', ''):<{col_w[2]}} {c:<{col_w[3]}} {i:<{col_w[4]}}"
            )
            lines.append(row)
        lines.append(sep)

    lines.append("")
    return lines


def _format_selection_metadata(analysis: FinalAnalysis) -> list[str]:
    meta = analysis.selection_metadata
    if not meta or not meta.auto_selected:
        return []
    lines = [
        f"{BOLD}Adaptive Module Selection:{RESET}",
        f"  {BOLD}Selected modules:{RESET} {', '.join(meta.selected_modules)}",
        f"  {BOLD}Reasoning:{RESET} {meta.selection_reasoning}",
    ]
    if meta.ad_hoc_modules:
        lines.append(f"  {BOLD}Ad-hoc modules:{RESET} {', '.join(m.name for m in meta.ad_hoc_modules)}")
    if meta.gap_check_reasoning:
        lines.append(f"  {BOLD}Gap check:{RESET} {meta.gap_check_reasoning}")
    lines.append("")
    return lines


def _format_resolution(res: ConflictResolution) -> list[str]:
    if res.modules:
        label = f"[{res.severity.upper()}] {' vs '.join(res.modules)} — {res.topic}"
    else:
        label = f"[RED FLAG] {res.topic}"
    return [
        f"  {BOLD}{label}{RESET}",
        f"  {BOLD}Verdict:{RESET} {res.verdict}",
        f"  {BOLD}Updated Recommendation:{RESET} {res.updated_recommendation}",
        "",
    ]


def _format_deep_research(analysis: FinalAnalysis) -> list[str]:
    if not analysis.conflict_resolutions:
        return []
    lines = [
        f"{BOLD}{'─'*60}",
        f"  Deep Research — Conflict & Flag Resolutions",
        f"{'─'*60}{RESET}\n",
    ]
    for res in analysis.conflict_resolutions:
        lines.extend(_format_resolution(res))
    return lines


def format_round_summary(module_outputs: list[ModuleOutput], round_num: int) -> str:
    lines = [f"\n{BOLD}{'='*60}", f"  Round {round_num} Summary", f"{'='*60}{RESET}\n"]
    for output in module_outputs:
        if output.round != round_num:
            continue
        lines.append(f"{CYAN}{BOLD}[{output.module_name.upper()}]{RESET}")
        for key, value in output.analysis.items():
            lines.append(f"  {key}: {value}")
        if output.flags:
            flags_str = ", ".join(_colorize_flag(f) for f in output.flags)
            lines.append(f"  Flags: {flags_str}")
        lines.append("")
    return "\n".join(lines)


def format_final_analysis(analysis: FinalAnalysis) -> str:
    lines = [
        f"\n{BOLD}{'='*60}",
        f"  FINAL ANALYSIS",
        f"{'='*60}{RESET}\n",
        f"{BOLD}Problem:{RESET} {analysis.problem}\n",
    ]

    lines.extend(_format_analysis_config(analysis))
    lines.extend(_format_selection_metadata(analysis))

    if analysis.deactivated_disclaimer:
        lines.append(f"{YELLOW}{BOLD}Note:{RESET} {YELLOW}{analysis.deactivated_disclaimer}{RESET}\n")

    if analysis.conflicts:
        lines.append(f"{BOLD}Conflicts Identified:{RESET}")
        for conflict in analysis.conflicts:
            lines.append(_format_conflict(conflict))
        lines.append("")

    if analysis.priority_flags:
        lines.append(f"{BOLD}Priority Flags:{RESET}")
        for flag in analysis.priority_flags:
            lines.append(f"  {_colorize_flag(flag)}")
        lines.append("")

    if analysis.synthesis:
        lines.append(f"{BOLD}Synthesis:{RESET}")
        lines.append(f"  {analysis.synthesis}\n")

    lines.extend(_format_deep_research(analysis))

    if analysis.recommendations:
        lines.append(f"{BOLD}Recommendations:{RESET}")
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    if analysis.sources:
        lines.append(f"{BOLD}Sources:{RESET}")
        for i, source in enumerate(analysis.sources, 1):
            lines.append(f"  [{i}] {source}")
        lines.append("")

    return "\n".join(lines)


def format_detailed_report(analysis: FinalAnalysis) -> str:
    lines = []

    # Header + Problem
    lines.append(f"\n{BOLD}{'='*60}")
    lines.append(f"  DETAILED ANALYSIS REPORT")
    lines.append(f"{'='*60}{RESET}\n")
    lines.append(f"{BOLD}Problem:{RESET} {analysis.problem}\n")

    lines.extend(_format_analysis_config(analysis))
    lines.extend(_format_selection_metadata(analysis))

    if analysis.deactivated_disclaimer:
        lines.append(f"{YELLOW}{BOLD}Note:{RESET} {YELLOW}{analysis.deactivated_disclaimer}{RESET}\n")

    # TL;DR — Final Analysis up front
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  TL;DR — Final Analysis")
    lines.append(f"{'─'*60}{RESET}\n")

    if analysis.priority_flags:
        lines.append(f"{BOLD}Priority Flags:{RESET}")
        for flag in analysis.priority_flags:
            lines.append(f"  {_colorize_flag(flag)}")
        lines.append("")

    if analysis.synthesis:
        lines.append(f"{BOLD}Synthesis:{RESET}")
        lines.append(f"  {analysis.synthesis}\n")

    if analysis.conflicts:
        lines.append(f"{BOLD}Conflicts Identified:{RESET}")
        for conflict in analysis.conflicts:
            lines.append(_format_conflict(conflict))
        lines.append("")

    if analysis.recommendations:
        lines.append(f"{BOLD}Recommendations:{RESET}")
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    # Transition into detailed evidence
    num_modules = len(set(o.module_name for o in analysis.module_outputs))
    num_rounds = len(set(o.round for o in analysis.module_outputs))
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Detailed Evidence")
    lines.append(f"{'─'*60}{RESET}\n")
    lines.append(
        f"  The conclusions above are based on {num_modules} independent"
        f" analysis modules, each running {num_rounds} rounds. In Round 1,"
        f" every module assessed the problem independently. In Round 2,"
        f" each module revised its analysis after reviewing the findings"
        f" of all other modules. The synthesis then reconciled agreements,"
        f" conflicts, and trade-offs into the final assessment.\n"
    )

    # Round 1 — Independent Analysis
    round1 = [o for o in analysis.module_outputs if o.round == 1]
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Round 1 — Independent Analysis")
    lines.append(f"{'─'*60}{RESET}\n")
    if round1:
        for output in round1:
            lines.extend(_format_module_detail(output))
    else:
        lines.append("  No Round 1 outputs recorded.\n")

    # Section 3: Round 2 — Cross-Module Revision
    round2 = [o for o in analysis.module_outputs if o.round == 2]
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Round 2 — Cross-Module Revision")
    lines.append(f"{'─'*60}{RESET}\n")
    if round2:
        for output in round2:
            lines.extend(_format_module_detail(output))
    else:
        lines.append("  No Round 2 outputs recorded.\n")

    # Section 4: Conflicts & Cross-Module Tensions
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Conflicts & Cross-Module Tensions")
    lines.append(f"{'─'*60}{RESET}\n")
    if analysis.conflicts:
        for conflict in analysis.conflicts:
            lines.append(_format_conflict(conflict))
        lines.append("")
    else:
        lines.append("  No conflicts identified.\n")

    # Deep Research Resolutions (optional)
    lines.extend(_format_deep_research(analysis))

    # Section 5: Recommendations
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Recommendations")
    lines.append(f"{'─'*60}{RESET}\n")
    if analysis.recommendations:
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")
    else:
        lines.append("  No recommendations provided.\n")

    # Section 6: Sources & References
    if analysis.sources:
        lines.append(f"{BOLD}{'─'*60}")
        lines.append(f"  Sources & References")
        lines.append(f"{'─'*60}{RESET}\n")
        for i, source in enumerate(analysis.sources, 1):
            lines.append(f"  [{i}] {source}")
        lines.append("")

    return "\n".join(lines)


def format_customer_report(analysis: FinalAnalysis) -> str:
    lines = []

    lines.append(f"\n{BOLD}{'='*60}")
    lines.append(f"  ANALYSIS REPORT")
    lines.append(f"{'='*60}{RESET}\n")
    lines.append(f"{BOLD}Problem:{RESET} {analysis.problem}\n")

    if analysis.deactivated_disclaimer:
        lines.append(f"{YELLOW}{BOLD}Note:{RESET} {YELLOW}{analysis.deactivated_disclaimer}{RESET}\n")

    if analysis.priority_flags:
        lines.append(f"{BOLD}Priority Flags:{RESET}")
        for flag in analysis.priority_flags:
            lines.append(f"  {_colorize_flag(flag)}")
        lines.append("")

    if analysis.synthesis:
        lines.append(f"{BOLD}Key Findings:{RESET}")
        lines.append(f"  {analysis.synthesis}\n")

    if analysis.recommendations:
        lines.append(f"{BOLD}Recommendations:{RESET}")
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    if analysis.sources:
        lines.append(f"{BOLD}Sources:{RESET}")
        for i, source in enumerate(analysis.sources, 1):
            lines.append(f"  [{i}] {source}")
        lines.append("")

    return "\n".join(lines)
