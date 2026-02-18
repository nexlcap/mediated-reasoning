import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from src.llm.client import ClaudeClient
from src.llm.prompts import (
    MODULE_SYSTEM_PROMPTS,
    build_followup_prompt,
    build_gap_check_prompt,
    build_module_selection_prompt,
    build_synthesis_prompt,
)
from src.models.schemas import AdHocModule, Conflict, FinalAnalysis, ModuleOutput, SearchContext, SelectionMetadata
from src.search import SearchPrePass
from src.modules import MODULE_REGISTRY
from src.modules.base_module import create_dynamic_module
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _strip_source_prefix(source: str) -> str:
    """Strip leading number prefix like '1. ' from source string."""
    return re.sub(r"^\d+\.\s*", "", source)


_URL_IN_SOURCE = re.compile(r"https?://[^\s]+")


def _extract_url_from_source(source: str) -> str:
    """Extract URL from a source string, or empty string if none."""
    m = _URL_IN_SOURCE.search(source)
    return m.group(0).rstrip(".,)\"'") if m else ""


def _remap_citations(text: str, index_map: Dict[int, int]) -> str:
    """Replace [N] citation markers with remapped global indices."""
    def _replace(m):
        old_idx = int(m.group(1))
        new_idx = index_map.get(old_idx, old_idx)
        return f"[{new_idx}]"
    return re.sub(r"\[(\d+)\]", _replace, text)


def _remap_analysis(analysis: Dict, index_map: Dict[int, int]) -> Dict:
    """Remap citation markers in all string values of an analysis dict."""
    remapped = {}
    for key, value in analysis.items():
        if isinstance(value, str):
            remapped[key] = _remap_citations(value, index_map)
        elif isinstance(value, list):
            remapped[key] = [
                _remap_citations(v, index_map) if isinstance(v, str) else v
                for v in value
            ]
        else:
            remapped[key] = value
    return remapped


def _consolidate_sources(
    all_outputs: List[ModuleOutput], synthesis_result: Dict
) -> tuple[List[str], List[ModuleOutput], Dict]:
    """Build a global deduplicated source list and remap all inline citations.

    Returns (global_sources, remapped_outputs, remapped_synthesis_fields).
    """
    # 1. Build global source list, deduplicating by URL (preferred) then text
    global_sources: List[str] = []
    seen_text: Dict[str, int] = {}   # stripped text -> 1-based global index
    seen_url: Dict[str, int] = {}    # URL -> 1-based global index

    def _add_source(raw_source: str) -> int:
        """Add source to global list (deduplicating by URL then text). Returns 1-based index."""
        stripped = _strip_source_prefix(raw_source)
        url = _extract_url_from_source(stripped)

        # URL match: same source already exists
        if url and url in seen_url:
            existing_idx = seen_url[url]
            # Upgrade to URL-bearing version if existing entry lacks URL
            if url not in global_sources[existing_idx - 1]:
                global_sources[existing_idx - 1] = stripped
            return existing_idx

        # Exact text match
        if stripped in seen_text:
            return seen_text[stripped]

        # New source
        global_sources.append(stripped)
        idx = len(global_sources)
        seen_text[stripped] = idx
        if url:
            seen_url[url] = idx
        return idx

    # Collect per-output local-to-global mappings
    output_maps: List[Dict[int, int]] = []
    for output in all_outputs:
        index_map: Dict[int, int] = {}
        for local_idx, raw_source in enumerate(output.sources, 1):
            index_map[local_idx] = _add_source(raw_source)
        output_maps.append(index_map)

    # Synthesis sources
    synthesis_map: Dict[int, int] = {}
    for local_idx, raw_source in enumerate(synthesis_result.get("sources", []), 1):
        synthesis_map[local_idx] = _add_source(raw_source)

    # 2. Remap inline citations in module outputs
    remapped_outputs = []
    for output, index_map in zip(all_outputs, output_maps):
        remapped_outputs.append(
            ModuleOutput(
                module_name=output.module_name,
                round=output.round,
                analysis=_remap_analysis(output.analysis, index_map),
                flags=[_remap_citations(f, index_map) for f in output.flags],
                sources=[],  # cleared — all sources consolidated at the end
                revised=output.revised,
            )
        )

    # 3. Remap inline citations in synthesis fields
    remapped_synthesis = {}
    remapped_synthesis["conflicts"] = [
        {**c, "description": _remap_citations(c.get("description", ""), synthesis_map)}
        for c in synthesis_result.get("conflicts", [])
        if isinstance(c, dict)
    ]
    for key in ("recommendations", "priority_flags"):
        remapped_synthesis[key] = [
            _remap_citations(item, synthesis_map)
            for item in synthesis_result.get(key, [])
        ]
    remapped_synthesis["synthesis"] = _remap_citations(
        synthesis_result.get("synthesis", ""), synthesis_map
    )

    return global_sources, remapped_outputs, remapped_synthesis


class Mediator:
    def __init__(self, client: ClaudeClient, weights: Optional[Dict[str, float]] = None, raci: Optional[Dict] = None, auto_select: bool = False, search: bool = True):
        self.client = client
        self.weights = weights or {}
        self.raci = raci
        self.auto_select = auto_select
        self.search = search
        self.selection_metadata: Optional[SelectionMetadata] = None

        if not auto_select:
            self._init_default_modules()

    def _init_default_modules(self):
        all_modules = [cls(self.client) for cls in MODULE_REGISTRY]
        self.deactivated_modules = [
            m.name for m in all_modules if self.weights.get(m.name, 1) == 0
        ]
        self.modules = [
            m for m in all_modules if m.name not in self.deactivated_modules
        ]

    def _select_modules(self, problem: str) -> None:
        """Run the two-step LLM pre-pass: module selection + gap check."""
        registry_by_name = {cls(None).name: cls for cls in MODULE_REGISTRY}

        try:
            # Step 1: Module selection
            system, user = build_module_selection_prompt(problem)
            selection_result = self.client.analyze(system, user)
            selected_names = selection_result.get("selected_modules", [])
            selection_reasoning = selection_result.get("reasoning", "")

            # Validate against known modules
            selected_names = [
                n for n in selected_names if n in MODULE_SYSTEM_PROMPTS
            ]
            if not selected_names:
                logger.warning("Auto-select returned no valid modules, falling back to defaults")
                self._init_default_modules()
                return

            # Step 2: Gap check
            system, user = build_gap_check_prompt(problem, selected_names)
            gap_result = self.client.analyze(system, user)
            gap_reasoning = gap_result.get("reasoning", "")
            raw_ad_hoc = gap_result.get("ad_hoc_modules", [])

            # Cap ad-hoc at 3, skip name collisions
            existing_names = set(MODULE_SYSTEM_PROMPTS.keys()) | set(selected_names)
            ad_hoc_modules: List[AdHocModule] = []
            for item in raw_ad_hoc[:3]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                prompt = item.get("system_prompt", "")
                if not name or not prompt:
                    continue
                if name in existing_names:
                    continue
                ad_hoc_modules.append(AdHocModule(name=name, system_prompt=prompt))
                existing_names.add(name)

            # Instantiate selected modules
            modules = []
            for name in selected_names:
                if name in registry_by_name:
                    modules.append(registry_by_name[name](self.client))
                else:
                    modules.append(
                        create_dynamic_module(name, MODULE_SYSTEM_PROMPTS[name], self.client)
                    )

            # Instantiate ad-hoc modules
            for adhoc in ad_hoc_modules:
                modules.append(
                    create_dynamic_module(adhoc.name, adhoc.system_prompt, self.client)
                )

            # Apply weight=0 deactivation
            self.deactivated_modules = [
                m.name for m in modules if self.weights.get(m.name, 1) == 0
            ]
            self.modules = [
                m for m in modules if m.name not in self.deactivated_modules
            ]

            self.selection_metadata = SelectionMetadata(
                auto_selected=True,
                selected_modules=[m.name for m in self.modules],
                selection_reasoning=selection_reasoning,
                gap_check_reasoning=gap_reasoning,
                ad_hoc_modules=ad_hoc_modules,
            )

        except Exception as e:
            logger.error("Auto-select failed (%s), falling back to defaults", e)
            self._init_default_modules()

    def _run_round1(self, module, problem: str, searcher=None) -> ModuleOutput:
        return module.run_round1(problem, searcher)

    def _run_round2(self, module, problem: str, round1_dicts: list, searcher=None) -> ModuleOutput:
        return module.run_round2(problem, round1_dicts, searcher)

    def analyze(self, problem: str) -> FinalAnalysis:
        if self.auto_select:
            self._select_modules(problem)

        # Create searcher once; each module fetches its own domain-specific sources
        searcher = SearchPrePass(self.client) if self.search else None

        # Round 1: Independent analysis (parallel, each module searches its own domain)
        logger.info("Starting Round 1: Independent Analysis")
        round1_outputs: List[ModuleOutput] = []
        with ThreadPoolExecutor(max_workers=len(self.modules)) as executor:
            future_to_module = {
                executor.submit(self._run_round1, module, problem, searcher): module
                for module in self.modules
            }
            for future in as_completed(future_to_module):
                module = future_to_module[future]
                try:
                    output = future.result()
                    round1_outputs.append(output)
                except Exception as e:
                    logger.error("Module %s failed in Round 1: %s", module.name, e)
        # Preserve deterministic ordering by module registry order
        module_order = {m.name: i for i, m in enumerate(self.modules)}
        round1_outputs.sort(key=lambda o: module_order[o.module_name])

        # Round 2: Informed revision (parallel)
        logger.info("Starting Round 2: Informed Revision")
        round1_dicts = [o.model_dump() for o in round1_outputs]
        round1_names = {o.module_name for o in round1_outputs}
        eligible_modules = [m for m in self.modules if m.name in round1_names]
        round2_outputs: List[ModuleOutput] = []
        with ThreadPoolExecutor(max_workers=len(eligible_modules) or 1) as executor:
            future_to_module = {
                executor.submit(self._run_round2, module, problem, round1_dicts, searcher): module
                for module in eligible_modules
            }
            for future in as_completed(future_to_module):
                module = future_to_module[future]
                try:
                    output = future.result()
                    round2_outputs.append(output)
                except Exception as e:
                    logger.error("Module %s failed in Round 2: %s", module.name, e)
        # Preserve deterministic ordering by module registry order
        round2_outputs.sort(key=lambda o: module_order[o.module_name])

        # Round 3: Synthesis
        logger.info("Starting Round 3: Synthesis")
        all_outputs = round1_outputs + round2_outputs

        synthesis_result = {}
        if all_outputs:
            all_output_dicts = [o.model_dump() for o in all_outputs]
            system, user = build_synthesis_prompt(
                problem, all_output_dicts,
                weights=self.weights,
                deactivated_modules=self.deactivated_modules,
                raci=self.raci,
            )
            try:
                synthesis_result = self.client.analyze(system, user)
            except Exception as e:
                logger.error("Synthesis failed: %s", e)
        else:
            logger.error("All modules failed — no data to synthesize")

        # Consolidate sources and remap inline citations
        global_sources, remapped_outputs, remapped_synthesis = (
            _consolidate_sources(all_outputs, synthesis_result)
        )

        return FinalAnalysis(
            problem=problem,
            module_outputs=remapped_outputs,
            conflicts=[Conflict(**c) for c in remapped_synthesis["conflicts"]],
            synthesis=remapped_synthesis["synthesis"],
            recommendations=remapped_synthesis["recommendations"],
            priority_flags=remapped_synthesis["priority_flags"],
            sources=global_sources,
            deactivated_disclaimer=synthesis_result.get("deactivated_disclaimer", ""),
            raci_matrix=self.raci or {},
            selection_metadata=self.selection_metadata,
        )

    def followup(self, analysis: FinalAnalysis, question: str) -> str:
        system, user = build_followup_prompt(analysis.problem, analysis, question)
        return self.client.chat(system, user)
