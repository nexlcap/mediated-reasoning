from typing import Dict, List, Optional


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

IMPORTANT: Use numbered inline citations like [1], [2], etc. within your analysis text, findings, opportunities, risks, and flags to reference specific sources. Each citation number must correspond to the matching numbered entry in the "sources" array. Every claim backed by data should have a citation.
"""


def build_round1_prompt(module_name: str, problem: str) -> tuple[str, str]:
    system = MODULE_SYSTEM_PROMPTS[module_name]
    user = (
        f"Analyze this problem/idea independently:\n\n"
        f"{problem}\n\n"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )
    return system, user


def build_round2_prompt(
    module_name: str, problem: str, round1_outputs: List[Dict]
) -> tuple[str, str]:
    system = MODULE_SYSTEM_PROMPTS[module_name] + (
        "\n\nYou are now in Round 2. You have seen the other modules' Round 1 analyses. "
        "Revise your analysis considering their perspectives. Note any agreements, "
        "disagreements, or new insights from cross-module review."
    )
    other_outputs = [o for o in round1_outputs if o["module_name"] != module_name]
    user = (
        f"Original problem:\n{problem}\n\n"
        f"Other modules' Round 1 analyses:\n\n"
        f"{_format_round1_outputs(other_outputs)}\n\n"
        f"Now provide your revised analysis for the {module_name} perspective.\n\n"
        f"{JSON_SCHEMA_INSTRUCTION}"
    )
    return system, user


def build_synthesis_prompt(
    problem: str,
    all_outputs: List[Dict],
    weights: Optional[Dict[str, float]] = None,
    deactivated_modules: Optional[List[str]] = None,
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
    if deactivated_modules:
        names = ", ".join(deactivated_modules)
        deactivated_instruction = (
            f"\n\nIMPORTANT: The following modules were deactivated by the user: {names}. "
            "You MUST include a disclaimer in your synthesis stating that these modules "
            "were deactivated and their perspectives are not reflected in this analysis."
        )

    user = (
        f"Original problem:\n{problem}\n\n"
        f"All module analyses (Rounds 1 and 2):\n\n"
        f"{_format_round1_outputs(all_outputs, weights=weights)}\n\n"
        "Synthesize these analyses into a final assessment.\n\n"
        f"{weight_instruction}{deactivated_instruction}\n\n"
        "Return your response as a JSON object with exactly these fields:\n"
        '{\n'
        '  "conflicts": ["conflict between modules [1]", ...],\n'
        '  "synthesis": "Overall synthesized assessment paragraph with inline citations [1][2]",\n'
        '  "recommendations": ["recommendation 1 [3]", ...],\n'
        '  "priority_flags": ["red: critical issue [1]", "yellow: caution", "green: positive"],\n'
        '  "sources": ["1. Source name", "2. Source name", ...]\n'
        '}\n\n'
        'IMPORTANT: Use numbered inline citations like [1], [2], etc. within your '
        'synthesis, conflicts, recommendations, and flags to reference specific sources. '
        'Each citation number must correspond to the matching numbered entry in the '
        '"sources" array. Every claim backed by data should have a citation.'
    )
    return system, user
