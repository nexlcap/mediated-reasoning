from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.schemas import FinalAnalysis


def _format_round1_outputs(
    round1_outputs: List[Dict],
    brief: bool = False,
) -> str:
    """Serialise Round 1 outputs for inclusion in prompts.

    brief=True (used for R2 cross-agent context): only summary + flags.
    brief=False (default, used for synthesis): full analysis dict.
    """
    sections = []
    for output in round1_outputs:
        name = output['agent_name']
        header = f"--- {name.upper()} AGENT ---"
        if brief:
            summary = output.get('analysis', {}).get('summary', '')
            sections.append(
                f"{header}\n"
                f"Summary: {summary}\n"
                f"Flags: {output['flags']}\n"
            )
        else:
            sections.append(
                f"{header}\n"
                f"Analysis: {output['analysis']}\n"
                f"Flags: {output['flags']}\n"
            )
    return "\n".join(sections)


# --- System prompts per agent ---
# Populated at runtime by create_dynamic_agent(); empty at import time.
AGENT_SYSTEM_PROMPTS: dict = {}


def _agent_json_instruction(has_search_context: bool) -> str:
    """Return the JSON schema instruction for agent prompts.

    When search context is present, agents must cite exclusively from the
    provided grounded sources. When absent, sources must be empty — fabricating
    source names or URLs is never acceptable.
    """
    if has_search_context:
        sources_field = '"sources": ["1. Title — https://url", "2. Title — https://url", ...]'
        sources_rule = (
            "SOURCES (STRICT): Your \"sources\" array must contain ONLY entries copied "
            "verbatim from the Grounded Research Context above — Title and full URL exactly "
            "as listed. Do NOT add sources from training knowledge or memory. "
            "Every specific statistic, percentage, market figure, date, or named claim "
            "MUST have an inline [N] citation from the provided context. "
            "Unsupported claims must be omitted or prefixed with \"(unverified)\"."
        )
    else:
        sources_field = '"sources": []'
        sources_rule = (
            "SOURCES (STRICT): No research context was provided, so your \"sources\" array "
            "MUST BE EMPTY. Do not fabricate source titles, URLs, or publication names. "
            "Do not use inline [N] citation markers. Analytical judgements are fine; "
            "invented citations are not."
        )

    return (
        "Return your response as a JSON object with exactly these fields:\n"
        "{\n"
        '  "analysis": {\n'
        '    "summary": "Brief overall assessment",\n'
        '    "key_findings": ["finding 1 [1]", "finding 2 [2]", ...],\n'
        '    "opportunities": ["opportunity 1 [3]", ...],\n'
        '    "risks": ["risk 1 [4]", ...]\n'
        "  },\n"
        '  "flags": ["red: critical issue [1]", "yellow: caution [2]", "green: positive signal"],\n'
        f'  {sources_field}\n'
        "}\n\n"
        f"{sources_rule}"
        "\n\nCONCISENESS: Maximum 5 items per array. One sentence per item. Omit minor points."
    )


# Keep as a constant for any existing callers that reference it directly
JSON_SCHEMA_INSTRUCTION = _agent_json_instruction(has_search_context=True)


def build_round1_prompt(agent_name: str, problem: str, search_context=None) -> tuple[str, str]:
    system = AGENT_SYSTEM_PROMPTS[agent_name]
    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"
    user = (
        f"Analyze this problem/idea independently:\n\n"
        f"{problem}\n\n"
        f"{search_section}"
        f"{_agent_json_instruction(has_search_context=bool(search_context))}"
    )
    return system, user


def build_round2_prompt(
    agent_name: str, problem: str, round1_outputs: List[Dict], search_context=None
) -> tuple[str, str]:
    system = AGENT_SYSTEM_PROMPTS[agent_name] + (
        "\n\nYou are now in Round 2. You have seen the other agents' Round 1 analyses. "
        "Revise your analysis considering their perspectives. Note any agreements, "
        "disagreements, or new insights from cross-agent review. "
        "IMPORTANT: Do not introduce new specific statistics, percentages, version numbers, "
        "dates, or named metrics that are not present in your Round 1 analysis or in the "
        "Grounded Research Context provided below. Any new concrete figure you include MUST "
        "have an inline [N] citation from that context. Do not invent numbers from training "
        "memory. Do not soften or retract critical findings from your Round 1 analysis — "
        "if you disagree with other agents, state the disagreement explicitly."
    )
    other_outputs = [o for o in round1_outputs if o["agent_name"] != agent_name]
    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"
    user = (
        f"Original problem:\n{problem}\n\n"
        f"Other agents' Round 1 analyses:\n\n"
        f"{_format_round1_outputs(other_outputs, brief=True)}\n\n"
        f"{search_section}"
        f"Now provide your revised analysis for the {agent_name} perspective.\n\n"
        f"{_agent_json_instruction(has_search_context=bool(search_context))}"
    )
    return system, user


def build_synthesis_prompt(
    problem: str,
    all_outputs: List[Dict],
    search_context=None,
    global_sources: Optional[List[str]] = None,
) -> tuple[str, str]:
    system = (
        "You are a senior strategic advisor synthesizing multiple expert analyses. "
        "Identify conflicts between agents, surface critical flags, and produce "
        "actionable recommendations. "
        "Respond with ONLY valid JSON, no other text."
    )

    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"

    source_list_section = ""
    if global_sources:
        formatted = "\n".join(f"[{i}] {s}" for i, s in enumerate(global_sources, 1))
        source_list_section = (
            f"CONSOLIDATED SOURCE LIST — these are the ONLY valid sources "
            f"(already numbered [1]–[{len(global_sources)}]):\n"
            f"{formatted}\n\n"
        )

    if global_sources:
        sources_instruction = (
            f'CRITICAL: Only cite sources using the numbers [1]–[{len(global_sources)}] '
            f'from the Consolidated Source List above. Do NOT invent or add new sources. '
            f'Your "sources" array MUST BE EMPTY — all sources are already listed above.'
        )
    else:
        sources_instruction = (
            'IMPORTANT: Use numbered inline citations like [1], [2], etc. within your '
            'synthesis, conflicts, recommendations, and flags to reference specific sources. '
            'Each citation number must correspond to the matching numbered entry in the '
            '"sources" array. Every claim backed by data should have a citation.'
        )
        if search_context:
            sources_instruction += (
                ' Only cite sources from the Grounded Research Context provided above — '
                'do not fabricate new sources. Your "sources" array must only contain '
                'entries from that list (title + URL).'
            )

    sources_field = (
        '  "sources": []\n'
        if global_sources else
        '  "sources": ["1. Title — URL", "2. Title — URL", ...]\n'
    )

    user = (
        f"Original problem:\n{problem}\n\n"
        f"All agent analyses (Rounds 1 and 2):\n\n"
        f"{_format_round1_outputs(all_outputs)}\n\n"
        f"{search_section}"
        f"{source_list_section}"
        "Synthesize these analyses into a final assessment.\n\n"
        "CONFLICT ARBITRATION: For each conflict, set \"arbitration.authority\" to the agent "
        "whose core domain makes it the most credible voice on that specific topic (e.g. cost "
        "owns financial estimates, tech owns implementation feasibility, legal owns compliance). "
        "Write a one-sentence \"arbitration.reasoning\" explaining why. This guides the "
        "synthesis but does not silence the other agent's findings.\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        '{\n'
        '  "conflicts": [\n'
        '    {"agents": ["market", "cost"], "topic": "burn rate", '
        '"description": "Market sees high demand but cost flags high burn rate [1][2]", '
        '"severity": "high", '
        '"arbitration": {"authority": "cost", "reasoning": "Cost owns financial modelling; market\'s estimate is directional only."}},\n'
        '    ...\n'
        '  ],\n'
        '  "synthesis": "Overall synthesized assessment paragraph with inline citations [1][2]",\n'
        '  "recommendations": ["recommendation 1 [3]", ...],\n'
        '  "priority_flags": ["red: critical issue [1]", "yellow: caution", "green: positive"],\n'
        '  "tldr_label": "Top 3 Actions",\n'
        '  "tldr_items": ["one punchy insight", "one punchy insight", "one punchy insight"],\n'
        f'{sources_field}'
        '}\n\n'
        'TLDR FIELDS:\n'
        '- "tldr_label": pick the label that best fits the question — '
        '"Top 3 Actions" for decision/execution questions, '
        '"Top 3 Findings" for research/investigative questions, '
        '"Top 3 Recommendations" for strategy/advisory questions.\n'
        '- "tldr_items": exactly 3 tight, citation-free sentences (no [N] references) '
        'a reader can grasp in 10 seconds — the clearest insight from each of the top three themes.\n\n'
        f'{sources_instruction}'
    )
    return system, user


def build_resolution_prompt(
    problem: str,
    topic: str,
    description: str,
    agents: List[str],
    agent_positions: Dict[str, str],
    search_context=None,
) -> tuple[str, str]:
    """Build a prompt to resolve a single conflict or red flag with fresh evidence."""
    system = (
        "You are a research expert resolving specific conflicts and critical issues "
        "identified in a multi-perspective analysis. Given fresh evidence from web search, "
        "provide an evidence-based verdict and a concrete updated recommendation. "
        "Respond with ONLY valid JSON, no other text."
    )

    label = "CONFLICT" if agents else "CRITICAL FLAG"
    agents_text = f" (between {' vs '.join(agents)})" if agents else ""

    positions_section = ""
    if agent_positions:
        parts = [
            f"{name.upper()} AGENT POSITION:\n{pos}"
            for name, pos in agent_positions.items()
            if pos
        ]
        if parts:
            positions_section = "\n\n".join(parts) + "\n\n"

    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"

    sources_instruction = (
        'Use [N] inline citations referencing the Grounded Research Context above. '
        'Copy sources verbatim as "Title — URL" into the "sources" array. '
        'Do NOT add sources from training knowledge or memory.'
        if search_context else
        'No research context was provided. Your "sources" array MUST BE EMPTY. '
        'Do not fabricate source titles or URLs. Do not use [N] citation markers.'
    )

    user = (
        f"Problem being analyzed: {problem}\n\n"
        f"{label}{agents_text}: {topic}\n"
        f"Description: {description}\n\n"
        f"{positions_section}"
        f"{search_section}"
        f"Based on the evidence above, resolve this {label.lower()}.\n\n"
        "Return a JSON object with exactly these fields:\n"
        "{\n"
        '  "verdict": "Which position does the evidence support, or what does the '
        'evidence show about this issue? Be specific. Include inline citations [N].",\n'
        '  "updated_recommendation": "A concrete, specific action step more precise '
        'than the original recommendations. Include inline citations [N].",\n'
        '  "sources": ["1. Title — URL", ...]\n'
        "}\n\n"
        f"{sources_instruction}"
    )
    return system, user


def build_dynamic_agent_generation_prompt(problem: str) -> tuple[str, str]:
    system = (
        "You are an expert problem decomposer. Given any problem or decision, you design "
        "a custom panel of specialist analysts whose combined perspectives illuminate every "
        "material dimension of that problem. You do NOT draw from a fixed list — you invent "
        "the exact specialist roles that best fit this specific situation. "
        "Respond with ONLY valid JSON, no other text."
    )
    user = (
        f"Problem to analyze:\n{problem}\n\n"
        "Design a panel of 3-8 specialist analysts for this problem. Each specialist "
        "must be unique and non-overlapping.\n\n"
        "IMPORTANT — two-pass composition rule:\n"
        "1. EXPLICIT first: if the problem explicitly calls out specific aspects to consider "
        "(e.g. 'consider environmental impact', 'focus on legal risks', 'think about team dynamics'), "
        "those aspects MUST each have a dedicated specialist. Lock these in first.\n"
        "2. CORE second: fill remaining slots (up to the 3-8 total) with the most analytically "
        "valuable perspectives for the core question — do NOT displace a core perspective "
        "(e.g. market fit, financial viability, technical feasibility) just to accommodate "
        "an explicitly requested one. Add it on top instead.\n\n"
        "Name each specialist using a short snake_case identifier (e.g. 'enterprise_sales_motion', "
        "'b2b_pricing_strategy'). The identifier becomes the agent's label in the final report.\n\n"
        "For each specialist, write a system prompt that:\n"
        "- Opens with \"You are a [role] expert.\"\n"
        "- States the specific lens they apply (2-3 sentences)\n"
        "- Ends exactly with: \"Respond with ONLY valid JSON, no other text.\"\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        "{\n"
        '  "agents": [\n'
        '    {"name": "specialist_name", "system_prompt": "You are a ... expert. ... Respond with ONLY valid JSON, no other text."},\n'
        "    ...\n"
        "  ],\n"
        '  "reasoning": "One sentence explaining the panel composition logic."\n'
        "}"
    )
    return system, user



def build_gap_check_prompt(
    problem: str, selected_agents: list[dict]
) -> tuple[str, str]:
    system = (
        "You are an expert at identifying analytical blind spots. "
        "Given a problem and a specialist panel already assembled, identify if any "
        "critical perspectives are missing. "
        "Respond with ONLY valid JSON, no other text."
    )
    panel_lines = "\n".join(
        f"- {m['name']}: {m['system_prompt'].split('.')[0]}."
        for m in selected_agents
        if m.get("name") and m.get("system_prompt")
    )
    user = (
        f"Problem to analyze:\n{problem}\n\n"
        f"Specialist panel already assembled:\n{panel_lines}\n\n"
        "Are any analytically significant perspectives missing? Only propose additional "
        "specialists if the gap would change a recommendation or surface an unseen risk.\n\n"
        "You may propose up to 3 additional specialists in the same format:\n"
        '{"name": "...", "system_prompt": "You are a ... expert. ... Respond with ONLY valid JSON, no other text."}\n\n'
        "Return your response as a JSON object with exactly these fields:\n"
        "{\n"
        '  "gaps_identified": true/false,\n'
        '  "reasoning": "Explanation of gaps found or why coverage is sufficient",\n'
        '  "ad_hoc_agents": [...]\n'
        "}"
    )
    return system, user


def build_followup_prompt(
    problem: str, analysis: "FinalAnalysis", question: str
) -> tuple[str, str]:
    system = (
        "You are a senior strategic advisor. You have completed a multi-perspective "
        "analysis of a problem. The analysis below is your grounding context — use it "
        "to stay consistent with what was already concluded. Then draw on your own "
        "expertise and general knowledge to give a concrete, actionable answer to the "
        "follow-up question. Do not refuse to answer just because the analysis lacks "
        "specific data — reason from first principles and your domain knowledge where "
        "needed, and be explicit when you are going beyond the analysis."
    )

    # Summarize agent outputs (prefer round 2 when available)
    agent_sections = []
    for output in analysis.agent_outputs:
        if output.round == 2 or not any(
            o.agent_name == output.agent_name and o.round == 2
            for o in analysis.agent_outputs
        ):
            summary = output.analysis.get("summary", "")
            agent_sections.append(f"- {output.agent_name}: {summary}")
    agents_text = "\n".join(agent_sections)

    conflicts_text = "\n".join(
        f"- {c.topic} ({', '.join(c.agents)}): {c.description}"
        for c in analysis.conflicts
    )

    recommendations_text = "\n".join(
        f"- {r}" for r in analysis.recommendations
    )

    user = (
        f"Problem: {problem}\n\n"
        f"Synthesis:\n{analysis.synthesis}\n\n"
        f"Agent summaries:\n{agents_text}\n\n"
        f"Conflicts:\n{conflicts_text}\n\n"
        f"Recommendations:\n{recommendations_text}\n\n"
        f"Follow-up question: {question}"
    )
    return system, user
