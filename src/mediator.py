import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from src.llm.client import ClaudeClient
from src.llm.prompts import build_synthesis_prompt
from src.models.schemas import FinalAnalysis, ModuleOutput
from src.modules import MODULE_REGISTRY
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _strip_source_prefix(source: str) -> str:
    """Strip leading number prefix like '1. ' from source string."""
    return re.sub(r"^\d+\.\s*", "", source)


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
    # 1. Build global source list, deduplicating by stripped text
    global_sources: List[str] = []
    seen: Dict[str, int] = {}  # stripped source text -> 1-based global index

    # Collect per-output local-to-global mappings
    output_maps: List[Dict[int, int]] = []
    for output in all_outputs:
        index_map: Dict[int, int] = {}
        for local_idx, raw_source in enumerate(output.sources, 1):
            stripped = _strip_source_prefix(raw_source)
            if stripped not in seen:
                global_sources.append(stripped)
                seen[stripped] = len(global_sources)
            index_map[local_idx] = seen[stripped]
        output_maps.append(index_map)

    # Synthesis sources
    synthesis_map: Dict[int, int] = {}
    for local_idx, raw_source in enumerate(
        synthesis_result.get("sources", []), 1
    ):
        stripped = _strip_source_prefix(raw_source)
        if stripped not in seen:
            global_sources.append(stripped)
            seen[stripped] = len(global_sources)
        synthesis_map[local_idx] = seen[stripped]

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
    for key in ("conflicts", "recommendations", "priority_flags"):
        remapped_synthesis[key] = [
            _remap_citations(item, synthesis_map)
            for item in synthesis_result.get(key, [])
        ]
    remapped_synthesis["synthesis"] = _remap_citations(
        synthesis_result.get("synthesis", ""), synthesis_map
    )

    return global_sources, remapped_outputs, remapped_synthesis


class Mediator:
    def __init__(self, client: ClaudeClient, weights: Optional[Dict[str, float]] = None):
        self.client = client
        self.weights = weights or {}
        all_modules = [cls(client) for cls in MODULE_REGISTRY]
        self.deactivated_modules = [
            m.name for m in all_modules if self.weights.get(m.name, 1) == 0
        ]
        self.modules = [
            m for m in all_modules if m.name not in self.deactivated_modules
        ]

    def _run_round1(self, module, problem: str) -> ModuleOutput:
        return module.run_round1(problem)

    def _run_round2(self, module, problem: str, round1_dicts: list) -> ModuleOutput:
        return module.run_round2(problem, round1_dicts)

    def analyze(self, problem: str) -> FinalAnalysis:
        # Round 1: Independent analysis (parallel)
        logger.info("Starting Round 1: Independent Analysis")
        round1_outputs: List[ModuleOutput] = []
        with ThreadPoolExecutor(max_workers=len(self.modules)) as executor:
            future_to_module = {
                executor.submit(self._run_round1, module, problem): module
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
                executor.submit(self._run_round2, module, problem, round1_dicts): module
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
            conflicts=remapped_synthesis["conflicts"],
            synthesis=remapped_synthesis["synthesis"],
            recommendations=remapped_synthesis["recommendations"],
            priority_flags=remapped_synthesis["priority_flags"],
            sources=global_sources,
        )
