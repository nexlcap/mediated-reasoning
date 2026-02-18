from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.schemas import FinalAnalysis


def _format_round1_outputs(
    round1_outputs: List[Dict], weights: Optional[Dict[str, float]] = None
) -> str:
    sections = []
    for output in round1_outputs:
        name = output['module_name']
        weight = (weights or {}).get(name, 1)
        header = f"--- {name.upper()} MODULE"
        if weight != 1:
            header += f" (Weight: {weight}x)"
        header += " ---"
        sections.append(
            f"{header}\n"
            f"Analysis: {output['analysis']}\n"
            f"Flags: {output['flags']}\n"
        )
    return "\n".join(sections)


# --- System prompts per module ---

MODULE_SYSTEM_PROMPTS = {
    "market": (
        "You are a market analysis expert. Evaluate the given problem/idea from a "
        "market perspective: market size, competitive landscape, customer demand, "
        "product-market fit, and go-to-market strategy. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "tech": (
        "You are a technical feasibility expert. Evaluate the given problem/idea from a "
        "technical perspective: technology stack, implementation complexity, development "
        "timeline, technical risks, and dependencies. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "cost": (
        "You are a financial analysis expert. Evaluate the given problem/idea from a "
        "financial perspective: initial investment, operating costs, revenue projections, "
        "break-even analysis, and funding requirements. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "legal": (
        "You are a legal and compliance expert. Evaluate the given problem/idea from a "
        "legal perspective: regulatory requirements, legal risks, compliance needs, "
        "liability concerns, and intellectual property considerations. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "scalability": (
        "You are a scalability and growth expert. Evaluate the given problem/idea from a "
        "scaling perspective: growth potential, infrastructure scaling, team scaling, "
        "operational complexity at scale, and bottlenecks. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "political": (
        "You are a political and regulatory environment expert. Evaluate the given problem/idea from a "
        "political perspective: government policy, political stability, institutional readiness, "
        "geopolitical factors, and public-sector dynamics. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "social": (
        "You are a social impact and demographics expert. Evaluate the given problem/idea from a "
        "societal perspective: societal impact, demographic trends, public acceptance, "
        "equity and inclusion, and community impact. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "environmental": (
        "You are an environmental and sustainability expert. Evaluate the given problem/idea from an "
        "ecological perspective: ecological footprint, climate risk, resource consumption, "
        "sustainability practices, and environmental regulations. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "ethics": (
        "You are an ethics and responsible innovation expert. Evaluate the given problem/idea from an "
        "ethical perspective: fairness, bias, privacy, rights, dual-use concerns, "
        "transparency, and accountability. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "operational": (
        "You are an operations and organizational expert. Evaluate the given problem/idea from an "
        "operational perspective: internal processes, team and HR considerations, supply chain, "
        "organizational structure, and change management. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "strategy": (
        "You are a business strategy expert. Evaluate the given problem/idea from a "
        "strategic perspective: business model, value proposition, competitive moats, "
        "market positioning, and partnership opportunities. "
        "Respond with ONLY valid JSON, no other text."
    ),
    "risk": (
        "You are a risk analysis expert. Evaluate the given problem/idea from a "
        "risk perspective: uncertainty assessment, downside scenarios, threat categorization, "
        "hedging strategies, and contingency planning. "
        "Respond with ONLY valid JSON, no other text."
    ),
}

ALL_MODULE_NAMES = sorted(MODULE_SYSTEM_PROMPTS.keys())

MODULE_DESCRIPTIONS = {
    "market": "Market size, competitive landscape, customer demand, product-market fit",
    "tech": "Technology stack, implementation complexity, technical risks, dependencies",
    "cost": "Financial analysis, investment, operating costs, revenue projections, break-even",
    "legal": "Regulatory requirements, legal risks, compliance, liability, IP",
    "scalability": "Growth potential, infrastructure scaling, team scaling, bottlenecks",
    "political": "Government policy, political stability, institutional readiness, geopolitics",
    "social": "Societal impact, demographics, public acceptance, equity, community impact",
    "environmental": "Ecological footprint, climate risk, resource consumption, sustainability",
    "ethics": "Fairness, bias, privacy, rights, dual-use, transparency, accountability",
    "operational": "Internal processes, team/HR, supply chain, org structure, change management",
    "strategy": "Business model, value proposition, competitive moats, positioning, partnerships",
    "risk": "Uncertainty, downside scenarios, threat categorization, hedging, contingency",
}

DEFAULT_RACI_MATRIX: Dict[str, Dict[str, Any]] = {
    "Market opportunity & demand": {
        "R": "market", "A": "market", "C": ["cost"], "I": ["risk"],
    },
    "Financial viability": {
        "R": "cost", "A": "cost", "C": ["market"], "I": ["risk"],
    },
    "Risk assessment": {
        "R": "risk", "A": "risk", "C": ["cost", "market"], "I": [],
    },
}

JSON_SCHEMA_INSTRUCTION = """
Return your response as a JSON object with exactly these fields:
{
  "analysis": {
    "summary": "Brief overall assessment",
    "key_findings": ["finding 1 [1]", "finding 2 [2]", ...],
    "opportunities": ["opportunity 1 [3]", ...],
    "risks": ["risk 1 [4]", ...]
  },
  "flags": ["red: critical issue description [1]", "yellow: caution description [2]", "green: positive signal description"],
  "sources": ["1. Source for finding 1", "2. Source for finding 2", ...]
}

IMPORTANT: Use numbered inline citations like [1], [2], etc. within your analysis text, findings, opportunities, risks, and flags to reference specific sources. Each citation number must correspond to the matching numbered entry in the "sources" array. Every claim backed by data should have a citation. When grounded research context is provided above, cite those real sources by their [N] numbers and include their titles and URLs in the sources array — do not fabricate sources.
"""


def build_round1_prompt(module_name: str, problem: str, search_context=None) -> tuple[str, str]:
    system = MODULE_SYSTEM_PROMPTS[module_name]
    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"
    user = (
        f"Analyze this problem/idea independently:\n\n"
        f"{problem}\n\n"
        f"{search_section}"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )
    return system, user


def build_round2_prompt(
    module_name: str, problem: str, round1_outputs: List[Dict], search_context=None
) -> tuple[str, str]:
    system = MODULE_SYSTEM_PROMPTS[module_name] + (
        "\n\nYou are now in Round 2. You have seen the other modules' Round 1 analyses. "
        "Revise your analysis considering their perspectives. Note any agreements, "
        "disagreements, or new insights from cross-module review."
    )
    other_outputs = [o for o in round1_outputs if o["module_name"] != module_name]
    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"
    user = (
        f"Original problem:\n{problem}\n\n"
        f"Other modules' Round 1 analyses:\n\n"
        f"{_format_round1_outputs(other_outputs)}\n\n"
        f"{search_section}"
        f"Now provide your revised analysis for the {module_name} perspective.\n\n"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )
    return system, user


def build_synthesis_prompt(
    problem: str,
    all_outputs: List[Dict],
    weights: Optional[Dict[str, float]] = None,
    deactivated_modules: Optional[List[str]] = None,
    raci: Optional[Dict[str, Dict[str, Any]]] = None,
    search_context=None,
) -> tuple[str, str]:
    system = (
        "You are a senior strategic advisor synthesizing multiple expert analyses. "
        "Identify conflicts between modules, surface critical flags, and produce "
        "actionable recommendations. "
        "Respond with ONLY valid JSON, no other text."
    )

    weight_instruction = ""
    if weights:
        active_weights = {k: v for k, v in weights.items() if v != 0}
        if active_weights:
            weight_instruction = (
                "\n\nModules with higher weights should carry proportionally more "
                "influence in your synthesis and recommendations."
            )

    deactivated_instruction = ""
    deactivated_field = ""
    if deactivated_modules:
        names = ", ".join(deactivated_modules)
        deactivated_instruction = (
            f"\n\nIMPORTANT: The following modules were deactivated by the user: {names}. "
            "You MUST include a disclaimer in your synthesis AND in the dedicated "
            '"deactivated_disclaimer" field stating which modules were deactivated '
            "and that their perspectives are not reflected in this analysis."
        )
        deactivated_field = (
            '  "deactivated_disclaimer": "Disclaimer noting which modules were '
            'deactivated and that their analysis is absent",\n'
        )

    raci_instruction = ""
    if raci:
        rows = []
        for topic, roles in raci.items():
            c = ", ".join(roles["C"]) if isinstance(roles["C"], list) else roles["C"]
            i = ", ".join(roles["I"]) if isinstance(roles["I"], list) else roles["I"]
            rows.append(f"| {topic} | {roles['R']} | {roles['A']} | {c} | {i} |")
        table = "\n".join(rows)
        raci_instruction = (
            "\n\nRACI MATRIX — Use this to resolve conflicts and prioritize recommendations:\n"
            "| Topic | Responsible | Accountable | Consulted | Informed |\n"
            "|---|---|---|---|---|\n"
            f"{table}\n"
            "When modules disagree, the Accountable module's position should carry the most "
            "weight for that topic. Consulted modules provide secondary input. "
            "Informed modules are noted but should not override the Accountable module."
        )

    search_section = ""
    if search_context:
        search_section = search_context.format_for_prompt() + "\n\n"

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

    user = (
        f"Original problem:\n{problem}\n\n"
        f"All module analyses (Rounds 1 and 2):\n\n"
        f"{_format_round1_outputs(all_outputs, weights=weights)}\n\n"
        f"{search_section}"
        "Synthesize these analyses into a final assessment.\n\n"
        f"{weight_instruction}{deactivated_instruction}{raci_instruction}\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        '{\n'
        f'{deactivated_field}'
        '  "conflicts": [\n'
        '    {"modules": ["market", "cost"], "topic": "burn rate", '
        '"description": "Market sees high demand but cost flags high burn rate [1][2]", '
        '"severity": "high"},\n'
        '    ...\n'
        '  ],\n'
        '  "synthesis": "Overall synthesized assessment paragraph with inline citations [1][2]",\n'
        '  "recommendations": ["recommendation 1 [3]", ...],\n'
        '  "priority_flags": ["red: critical issue [1]", "yellow: caution", "green: positive"],\n'
        '  "sources": ["1. Title — URL", "2. Title — URL", ...]\n'
        '}\n\n'
        f'{sources_instruction}'
    )
    return system, user


def build_module_selection_prompt(problem: str) -> tuple[str, str]:
    system = (
        "You are an expert at scoping multi-perspective analyses. "
        "Given a problem, you select which analysis modules are relevant. "
        "Respond with ONLY valid JSON, no other text."
    )

    module_list = "\n".join(
        f"- {name}: {MODULE_DESCRIPTIONS[name]}"
        for name in ALL_MODULE_NAMES
    )

    user = (
        f"Problem to analyze:\n{problem}\n\n"
        f"Available analysis modules:\n{module_list}\n\n"
        "Select 3-7 modules that are most relevant to this problem. "
        "Only include modules whose perspective adds meaningful value.\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        '{\n'
        '  "selected_modules": ["module1", "module2", ...],\n'
        '  "reasoning": "Brief explanation of why these modules were selected"\n'
        '}'
    )
    return system, user


def build_gap_check_prompt(
    problem: str, selected_module_names: list[str]
) -> tuple[str, str]:
    system = (
        "You are an expert at identifying analytical blind spots. "
        "Given a problem and a set of selected analysis modules, check whether "
        "any important perspectives are missing. "
        "Respond with ONLY valid JSON, no other text."
    )

    selected_list = ", ".join(selected_module_names)
    all_modules_list = "\n".join(
        f"- {name}: {MODULE_DESCRIPTIONS[name]}"
        for name in ALL_MODULE_NAMES
    )

    user = (
        f"Problem to analyze:\n{problem}\n\n"
        f"Already selected modules: {selected_list}\n\n"
        f"Full pool of available modules:\n{all_modules_list}\n\n"
        "Check if any significant analytical gaps remain. If so, you may propose "
        "up to 3 ad-hoc modules with custom system prompts to fill those gaps. "
        "Only propose ad-hoc modules if the gap is significant and not covered by "
        "the selected modules.\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        '{\n'
        '  "gaps_identified": true/false,\n'
        '  "reasoning": "Explanation of gaps found or why coverage is sufficient",\n'
        '  "ad_hoc_modules": [\n'
        '    {"name": "module_name", "system_prompt": "You are a ... expert. Evaluate ..."},\n'
        '    ...\n'
        '  ]\n'
        '}'
    )
    return system, user


def build_followup_prompt(
    problem: str, analysis: "FinalAnalysis", question: str
) -> tuple[str, str]:
    system = (
        "You are a senior strategic advisor. You have completed a multi-perspective "
        "analysis of a problem. Answer the user's follow-up question based on the "
        "analysis below. Be concise and direct."
    )

    # Summarize module outputs (prefer round 2 when available)
    module_sections = []
    for output in analysis.module_outputs:
        if output.round == 2 or not any(
            o.module_name == output.module_name and o.round == 2
            for o in analysis.module_outputs
        ):
            summary = output.analysis.get("summary", "")
            module_sections.append(f"- {output.module_name}: {summary}")
    modules_text = "\n".join(module_sections)

    conflicts_text = "\n".join(
        f"- {c.topic} ({', '.join(c.modules)}): {c.description}"
        for c in analysis.conflicts
    )

    recommendations_text = "\n".join(
        f"- {r}" for r in analysis.recommendations
    )

    user = (
        f"Problem: {problem}\n\n"
        f"Synthesis:\n{analysis.synthesis}\n\n"
        f"Module summaries:\n{modules_text}\n\n"
        f"Conflicts:\n{conflicts_text}\n\n"
        f"Recommendations:\n{recommendations_text}\n\n"
        f"Follow-up question: {question}"
    )
    return system, user
