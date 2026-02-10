from src.models.schemas import FinalAnalysis, ModuleOutput


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


def _colorize_flag(flag: str) -> str:
    lower = flag.lower()
    for level, color in FLAG_COLORS.items():
        if lower.startswith(level):
            return f"{color}{flag}{RESET}"
    return flag


def _format_module_detail(output: ModuleOutput) -> list[str]:
    lines = [f"{CYAN}{BOLD}[{output.module_name.upper()}]{RESET}"]
    for key, value in output.analysis.items():
        lines.append(f"  {BOLD}{key}:{RESET} {value}")
    if output.flags:
        flags_str = ", ".join(_colorize_flag(f) for f in output.flags)
        lines.append(f"  {BOLD}Flags:{RESET} {flags_str}")
    if output.sources:
        lines.append(f"  {BOLD}Sources:{RESET}")
        for source in output.sources:
            lines.append(f"    - {source}")
    lines.append("")
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

    if analysis.conflicts:
        lines.append(f"{BOLD}Conflicts Identified:{RESET}")
        for conflict in analysis.conflicts:
            lines.append(f"  - {conflict}")
        lines.append("")

    if analysis.priority_flags:
        lines.append(f"{BOLD}Priority Flags:{RESET}")
        for flag in analysis.priority_flags:
            lines.append(f"  {_colorize_flag(flag)}")
        lines.append("")

    if analysis.synthesis:
        lines.append(f"{BOLD}Synthesis:{RESET}")
        lines.append(f"  {analysis.synthesis}\n")

    if analysis.recommendations:
        lines.append(f"{BOLD}Recommendations:{RESET}")
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

    if analysis.sources:
        lines.append(f"{BOLD}Sources:{RESET}")
        for source in analysis.sources:
            lines.append(f"  - {source}")
        lines.append("")

    return "\n".join(lines)


def format_detailed_report(analysis: FinalAnalysis) -> str:
    lines = []

    # Header + Problem
    lines.append(f"\n{BOLD}{'='*60}")
    lines.append(f"  DETAILED ANALYSIS REPORT")
    lines.append(f"{'='*60}{RESET}\n")
    lines.append(f"{BOLD}Problem:{RESET} {analysis.problem}\n")

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
            lines.append(f"  - {conflict}")
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
            lines.append(f"  - {conflict}")
        lines.append("")
    else:
        lines.append("  No conflicts identified.\n")

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
        for source in analysis.sources:
            lines.append(f"  - {source}")
        lines.append("")

    return "\n".join(lines)
