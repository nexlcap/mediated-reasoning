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

    return "\n".join(lines)
