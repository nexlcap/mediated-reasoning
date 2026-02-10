from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from src.llm.client import ClaudeClient
from src.llm.prompts import build_synthesis_prompt
from src.models.schemas import FinalAnalysis, ModuleOutput
from src.modules import MODULE_REGISTRY
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Mediator:
    def __init__(self, client: ClaudeClient):
        self.client = client
        self.modules = [cls(client) for cls in MODULE_REGISTRY]

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
            system, user = build_synthesis_prompt(problem, all_output_dicts)
            try:
                synthesis_result = self.client.analyze(system, user)
            except Exception as e:
                logger.error("Synthesis failed: %s", e)
        else:
            logger.error("All modules failed — no data to synthesize")

        # Collect unique sources from all modules and synthesis
        seen = set()
        all_sources = []
        for output in all_outputs:
            for s in output.sources:
                if s not in seen:
                    seen.add(s)
                    all_sources.append(s)
        for s in synthesis_result.get("sources", []):
            if s not in seen:
                seen.add(s)
                all_sources.append(s)

        return FinalAnalysis(
            problem=problem,
            module_outputs=all_outputs,
            conflicts=synthesis_result.get("conflicts", []),
            synthesis=synthesis_result.get("synthesis", ""),
            recommendations=synthesis_result.get("recommendations", []),
            priority_flags=synthesis_result.get("priority_flags", []),
            sources=all_sources,
        )
