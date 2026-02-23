"""
Layer 1: Static prompt linting.

Calls every LLM prompt builder with representative inputs and asserts that
the required hallucination-constraint phrases are present.  Fast, zero cost,
no network — safe to run on every commit.
"""
import sys
from typing import List


def lint() -> List[str]:
    """Return a list of violation strings.  Empty list = all checks passed."""
    from src.llm.prompts import (
        _module_json_instruction,
        build_dynamic_module_generation_prompt,
        build_gap_check_prompt,
        build_synthesis_prompt,
        build_resolution_prompt,
        build_followup_prompt,
    )

    violations: List[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            violations.append(message)

    # --- Layer 1a: _module_json_instruction ---

    no_search = _module_json_instruction(has_search_context=False)
    check(
        "MUST BE EMPTY" in no_search,
        "_module_json_instruction(False) missing 'MUST BE EMPTY'",
    )
    check(
        "Do not fabricate" in no_search or "do not fabricate" in no_search,
        "_module_json_instruction(False) missing fabrication prohibition",
    )
    check(
        "Do not use inline [N]" in no_search or "Do not use [N]" in no_search or "citation markers" in no_search,
        "_module_json_instruction(False) missing [N] prohibition",
    )

    with_search = _module_json_instruction(has_search_context=True)
    check(
        "ONLY" in with_search or "verbatim" in with_search,
        "_module_json_instruction(True) missing verbatim-copy constraint",
    )
    check(
        "MUST have an inline [N]" in with_search or "MUST be cited" in with_search or "MUST have" in with_search,
        "_module_json_instruction(True) missing mandatory citation rule",
    )

    # --- Layer 1b: build_synthesis_prompt ---

    # Without global_sources → synthesis may cite normally
    _, user_no_global = build_synthesis_prompt("test problem", [], None, None, None, None)
    check(
        "sources" in user_no_global.lower(),
        "build_synthesis_prompt (no global_sources) missing sources field",
    )

    # With global_sources → must inject list and forbid new sources
    _, user_with_global = build_synthesis_prompt(
        "test problem", [], None, None, None,
        global_sources=["Source One — https://example.com/1"],
    )
    check(
        "CRITICAL" in user_with_global or "Only cite" in user_with_global,
        "build_synthesis_prompt (global_sources) missing CRITICAL citation constraint",
    )
    check(
        '"sources": []' in user_with_global,
        "build_synthesis_prompt (global_sources) must force empty sources array in schema",
    )
    check(
        "https://example.com/1" in user_with_global,
        "build_synthesis_prompt (global_sources) must inject the actual source list",
    )

    # --- Layer 1c: build_resolution_prompt ---

    # With search context
    from src.models.schemas import SearchContext, SearchResult
    sc = SearchContext(
        queries=["test"],
        results=[SearchResult(title="T", url="https://example.com", content="c")],
    )
    _, res_with = build_resolution_prompt("prob", "topic", "desc", ["a", "b"], {}, sc)
    check(
        "verbatim" in res_with or "ONLY" in res_with or "copy" in res_with.lower(),
        "build_resolution_prompt (with search) missing verbatim-copy constraint",
    )

    # Without search context
    _, res_without = build_resolution_prompt("prob", "topic", "desc", ["a", "b"], {}, None)
    check(
        "MUST BE EMPTY" in res_without or "must be empty" in res_without.lower(),
        "build_resolution_prompt (no search) missing 'MUST BE EMPTY' constraint",
    )

    # --- Layer 1e: build_dynamic_module_generation_prompt ---
    _, gen_user = build_dynamic_module_generation_prompt("Should I pivot to B2B?")
    check('"modules"' in gen_user, "build_dynamic_module_generation_prompt: missing 'modules' field")
    check('"reasoning"' in gen_user, "build_dynamic_module_generation_prompt: missing 'reasoning' field")
    check("snake_case" in gen_user, "build_dynamic_module_generation_prompt: missing snake_case name guidance")
    check("Respond with ONLY valid JSON" in gen_user, "build_dynamic_module_generation_prompt: missing JSON constraint for generated system prompts")
    check("3" in gen_user and "7" in gen_user, "build_dynamic_module_generation_prompt: missing 3-7 count guidance")

    sample_modules = [{"name": "enterprise_sales", "system_prompt": "You are an enterprise sales expert. Respond with ONLY valid JSON, no other text."}]
    _, gap_user = build_gap_check_prompt("B2B pivot", sample_modules)
    check("enterprise_sales" in gap_user, "build_gap_check_prompt: does not reference generated module names")
    check("ad_hoc_modules" in gap_user, "build_gap_check_prompt: missing 'ad_hoc_modules' field")
    check("gaps_identified" in gap_user, "build_gap_check_prompt: missing 'gaps_identified' field")

    # --- Layer 1d: build_followup_prompt ---

    from src.models.schemas import FinalAnalysis
    minimal = FinalAnalysis(problem="test")
    system, _ = build_followup_prompt("test problem", minimal, "a question")
    check(
        "grounding" in system.lower() or "context" in system.lower(),
        "build_followup_prompt system prompt missing grounding context reference",
    )
    check(
        "expertise" in system.lower() or "knowledge" in system.lower(),
        "build_followup_prompt system prompt missing expert reasoning allowance",
    )

    return violations


def main() -> int:
    violations = lint()
    if violations:
        print("PROMPT LINTER — FAILURES:")
        for v in violations:
            print(f"  ✗ {v}")
        return 1
    print("Prompt linter: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
