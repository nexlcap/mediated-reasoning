from src.models.schemas import Conflict, ConflictResolution, FinalAnalysis, AgentOutput


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
    agents = " vs ".join(conflict.agents)
    line = f"  - {color}[{severity_tag}]{reset} {agents} — {conflict.topic}: {conflict.description}"
    if conflict.arbitration:
        line += (
            f"\n    {BOLD}→ Authority:{RESET} {conflict.arbitration.authority}"
            f" — {conflict.arbitration.reasoning}"
        )
    return line


def _colorize_flag(flag: str) -> str:
    lower = flag.lower()
    for level, color in FLAG_COLORS.items():
        if lower.startswith(level):
            return f"{color}{flag}{RESET}"
    return flag


def _format_agent_detail(output: AgentOutput) -> list[str]:
    lines = [f"{CYAN}{BOLD}[{output.agent_name.upper()}]{RESET}"]
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
    """Render the Analysis Configuration block (agents, weights, RACI, search)."""
    lines = [f"{BOLD}Analysis Configuration:{RESET}"]

    # Active agents with weights
    active_agents = list(dict.fromkeys(
        o.agent_name for o in analysis.agent_outputs
    ))
    if active_agents:
        agent_parts = []
        for name in active_agents:
            w = analysis.weights.get(name, 1)
            agent_parts.append(f"{name} ({w}x)" if w != 1 else name)
        lines.append(f"  {BOLD}Agents:{RESET} {', '.join(agent_parts)}")

    # Deactivated agents
    deactivated = [
        name for name, w in analysis.weights.items()
        if w == 0 and name not in active_agents
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

    # Ad-hoc agents (from selection metadata)
    meta = analysis.selection_metadata
    if meta and meta.ad_hoc_agents:
        adhoc_names = ", ".join(m.name for m in meta.ad_hoc_agents)
        lines.append(f"  {BOLD}Ad-hoc agents:{RESET} {adhoc_names}")

    lines.append("")
    return lines


def _format_selection_metadata(analysis: FinalAnalysis) -> list[str]:
    meta = analysis.selection_metadata
    if not meta or not meta.auto_selected:
        return []
    lines = [
        f"{BOLD}Adaptive Agent Selection:{RESET}",
        f"  {BOLD}Selected agents:{RESET} {', '.join(meta.selected_agents)}",
        f"  {BOLD}Reasoning:{RESET} {meta.selection_reasoning}",
    ]
    if meta.ad_hoc_agents:
        lines.append(f"  {BOLD}Ad-hoc agents:{RESET} {', '.join(m.name for m in meta.ad_hoc_agents)}")
    if meta.gap_check_reasoning:
        lines.append(f"  {BOLD}Gap check:{RESET} {meta.gap_check_reasoning}")
    lines.append("")
    return lines


def _format_resolution(res: ConflictResolution) -> list[str]:
    if res.agents:
        label = f"[{res.severity.upper()}] {' vs '.join(res.agents)} — {res.topic}"
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


def format_round_summary(agent_outputs: list[AgentOutput], round_num: int) -> str:
    lines = [f"\n{BOLD}{'='*60}", f"  Round {round_num} Summary", f"{'='*60}{RESET}\n"]
    for output in agent_outputs:
        if output.round != round_num:
            continue
        lines.append(f"{CYAN}{BOLD}[{output.agent_name.upper()}]{RESET}")
        for key, value in output.analysis.items():
            lines.append(f"  {key}: {value}")
        if output.flags:
            flags_str = ", ".join(_colorize_flag(f) for f in output.flags)
            lines.append(f"  Flags: {flags_str}")
        lines.append("")
    return "\n".join(lines)


def _format_quality(analysis: FinalAnalysis) -> list[str]:
    from src.models.schemas import RunQuality
    q = analysis.quality
    if not isinstance(q, RunQuality):
        return []
    tier_color = {"good": GREEN, "degraded": YELLOW, "poor": RED}.get(q.tier, RESET)
    lines = [f"{BOLD}Run Quality:{RESET} {tier_color}{q.tier}{RESET} (score: {q.score:.2f})"]
    for w in q.warnings:
        lines.append(f"  {YELLOW}⚠  {w}{RESET}")
    lines.append("")
    return lines


def _format_audit(analysis: FinalAnalysis) -> list[str]:
    audit = analysis.audit
    if not audit:
        return []

    lines = [
        f"{BOLD}{'─'*60}",
        f"  Source & Integrity Audit",
        f"{'─'*60}{RESET}\n",
    ]

    def _status(passed: bool) -> str:
        return f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"

    lines.append(f"  Prompt constraints:  {_status(audit.layer1_passed)}")
    lines.append(f"  Citation integrity:  {_status(audit.layer2_passed)}")

    if audit.layer3_total:
        pct = int(100 * audit.layer3_ok / audit.layer3_total)
        warn = f"  {YELLOW}⚠ {len(audit.layer3_failures)} issue(s) below{RESET}" if audit.layer3_failures else ""
        lines.append(f"  URL reachability:    {audit.layer3_ok}/{audit.layer3_total} ({pct}%){warn}")

    if audit.layer4_ran:
        r4 = audit.layer4_results
        total = len(r4)
        supported = sum(1 for r in r4 if r.verdict == "SUPPORTED")
        if total:
            bad = total - supported
            warn = f"  {YELLOW}⚠ {bad} issue(s) below{RESET}" if bad else ""
            lines.append(f"  Grounding check:     {supported}/{total} supported{warn}")
        else:
            lines.append(f"  Grounding check:     No citations sampled")

    if audit.layer5_ran:
        r5 = audit.layer5_results
        total5 = len(r5)
        ok5 = sum(1 for r in r5 if r.ok)
        status5 = _status(ok5 == total5) if total5 else f"{YELLOW}No pairs found{RESET}"
        lines.append(f"  R1→R2 consistency:   {ok5}/{total5} agents consistent  {status5}" if total5 else f"  R1→R2 consistency:   {status5}")

    for v in audit.layer1_violations + audit.layer2_violations:
        lines.append(f"    {RED}✗ {v}{RESET}")

    for f in audit.layer3_failures:
        status = f.status or "ERR"
        lines.append(f"    {YELLOW}[{status}] {f.url}{RESET}")

    if audit.layer4_ran:
        icons = {"PARTIAL": "~", "UNSUPPORTED": "✗", "FETCH_FAILED": "?", "UNKNOWN": "?"}
        for r in audit.layer4_results:
            if r.verdict != "SUPPORTED":
                icon = icons.get(r.verdict, "?")
                lines.append(f"    {YELLOW}{icon} {r.citation} {r.verdict}: {r.sentence[:100]}…{RESET}")

    if audit.layer5_ran:
        for r in audit.layer5_results:
            if not r.ok:
                lines.append(f"    {YELLOW}[{r.agent}]{RESET}")
                for issue in r.issues:
                    lines.append(f"      {RED}✗ {issue}{RESET}")

    lines.append("")
    return lines


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

    lines.extend(_format_audit(analysis))
    lines.extend(_format_quality(analysis))

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
    num_agents = len(set(o.agent_name for o in analysis.agent_outputs))
    num_rounds = len(set(o.round for o in analysis.agent_outputs))
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Detailed Evidence")
    lines.append(f"{'─'*60}{RESET}\n")
    lines.append(
        f"  The conclusions above are based on {num_agents} independent"
        f" analysis agents, each running {num_rounds} rounds. In Round 1,"
        f" every agent assessed the problem independently. In Round 2,"
        f" each agent revised its analysis after reviewing the findings"
        f" of all other agents. The synthesis then reconciled agreements,"
        f" conflicts, and trade-offs into the final assessment.\n"
    )

    # Round 1 — Independent Analysis
    round1 = [o for o in analysis.agent_outputs if o.round == 1]
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Round 1 — Independent Analysis")
    lines.append(f"{'─'*60}{RESET}\n")
    if round1:
        for output in round1:
            lines.extend(_format_agent_detail(output))
    else:
        lines.append("  No Round 1 outputs recorded.\n")

    # Section 3: Round 2 — Cross-Agent Revision
    round2 = [o for o in analysis.agent_outputs if o.round == 2]
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Round 2 — Cross-Agent Revision")
    lines.append(f"{'─'*60}{RESET}\n")
    if round2:
        for output in round2:
            lines.extend(_format_agent_detail(output))
    else:
        lines.append("  No Round 2 outputs recorded.\n")

    # Section 4: Conflicts & Cross-Agent Tensions
    lines.append(f"{BOLD}{'─'*60}")
    lines.append(f"  Conflicts & Cross-Agent Tensions")
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

    lines.extend(_format_audit(analysis))

    return "\n".join(lines)


def _flag_md(flag: str) -> str:
    """Convert 'red: ...' flag to emoji + text for markdown rendering."""
    lower = flag.lower()
    if lower.startswith("red:"):
        return "🔴 " + flag[4:].strip()
    if lower.startswith("yellow:"):
        return "🟡 " + flag[7:].strip()
    if lower.startswith("green:"):
        return "🟢 " + flag[6:].strip()
    return flag


def format_core_md(analysis: FinalAnalysis) -> str:
    """Core result for the main canvas.
    Flow: critical signals → analysis → recommended actions.
    Sources are excluded — they live in the right sidebar.
    """
    parts: list[str] = []

    # Signals sorted red → yellow → green so the most urgent land first
    if analysis.priority_flags:
        red    = [f for f in analysis.priority_flags if f.lower().startswith("red")]
        yellow = [f for f in analysis.priority_flags if f.lower().startswith("yellow")]
        green  = [f for f in analysis.priority_flags if f.lower().startswith("green")]
        other  = [f for f in analysis.priority_flags
                  if not f.lower().startswith(("red", "yellow", "green"))]
        parts.append("## 🚦 Critical Signals")
        for flag in red + yellow + green + other:
            parts.append(f"- {_flag_md(flag)}")
        parts.append("")

    if analysis.synthesis:
        if parts:
            parts.append("---")
            parts.append("")
        parts.append("## 💡 Analysis")
        parts.append("")
        parts.append(analysis.synthesis)
        parts.append("")

    if analysis.recommendations:
        parts.append("---")
        parts.append("")
        parts.append("## ✅ Recommended Actions")
        parts.append("")
        for i, rec in enumerate(analysis.recommendations, 1):
            # Each recommendation as its own visual block
            parts.append(f"**{i}.** {rec}")
            parts.append("")

    return "\n".join(parts)


def format_sources_md(analysis: FinalAnalysis) -> str:
    """Sources section for the right sidebar."""
    if not analysis.sources:
        return ""
    parts = ["### 📚 Sources", ""]
    for i, src in enumerate(analysis.sources, 1):
        parts.append(f"**[{i}]** {src}")
        parts.append("")
    return "\n".join(parts)


def format_detail_md(analysis: FinalAnalysis, detailed: bool = False) -> str:
    """Collapsible detail panel: specialists → conflicts → deep research → agent analyses → quality.
    detailed=True also includes Round 1 outputs.
    """
    parts: list[str] = []

    # Specialist panel
    meta = analysis.selection_metadata
    if meta and meta.auto_selected:
        parts.append("### Specialists")
        parts.append(f"**Selected:** {', '.join(meta.selected_agents)}")
        if meta.selection_reasoning:
            parts.append(f"\n**Reasoning:** {meta.selection_reasoning}")
        if meta.ad_hoc_agents:
            parts.append(f"\n**Gap-check additions:** {', '.join(m.name for m in meta.ad_hoc_agents)}")
            if meta.gap_check_reasoning:
                parts.append(f"\n**Gap reasoning:** {meta.gap_check_reasoning}")
        parts.append("")

    # Conflicts
    if analysis.conflicts:
        parts.append("### Conflicts")
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}
        for c in analysis.conflicts:
            icon = severity_icon.get(c.severity, "")
            agents_str = " vs ".join(c.agents)
            parts.append(f"**{icon} [{c.severity.upper()}]** {agents_str} — {c.topic}")
            parts.append(f"> {c.description}")
            if c.arbitration:
                parts.append(
                    f"> → Authority: **{c.arbitration.authority}** — {c.arbitration.reasoning}"
                )
            parts.append("")

    # Deep research resolutions
    if analysis.conflict_resolutions:
        parts.append("### Deep Research Resolutions")
        for res in analysis.conflict_resolutions:
            if res.agents:
                label = f"[{res.severity.upper()}] {' vs '.join(res.agents)} — {res.topic}"
            else:
                label = f"[RED FLAG] {res.topic}"
            parts.append(f"**{label}**")
            parts.append(f"**Verdict:** {res.verdict}")
            parts.append(f"**Updated recommendation:** {res.updated_recommendation}")
            parts.append("")

    # Agent analyses — prefer R2; include R1 only when detailed=True
    r2_names = {o.agent_name for o in analysis.agent_outputs if o.round == 2}
    to_show = []
    for o in analysis.agent_outputs:
        if o.round == 2:
            to_show.append(o)
        elif o.round == 1 and (detailed or o.agent_name not in r2_names):
            to_show.append(o)

    if to_show:
        parts.append("### Specialist Analyses")
        for o in to_show:
            round_label = "*(Round 2 — revised)*" if o.round == 2 else "*(Round 1)*"
            parts.append(f"#### {o.agent_name} {round_label}")
            for key, value in o.analysis.items():
                if isinstance(value, list):
                    parts.append(f"**{key}:**")
                    for item in value:
                        parts.append(f"- {item}")
                else:
                    parts.append(f"**{key}:** {value}")
            if o.flags:
                parts.append(f"\n**Flags:** {', '.join(o.flags)}")
            parts.append("")

    # Quality gate
    q = analysis.quality
    if q:
        tier_icon = {"good": "✅", "degraded": "⚠️", "poor": "❌"}.get(q.tier, "")
        parts.append("### Quality")
        parts.append(f"{tier_icon} **{q.tier}** (score: {q.score:.2f})")
        for w in q.warnings:
            parts.append(f"- ⚠️ {w}")
        parts.append("")

    return "\n".join(parts)


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
