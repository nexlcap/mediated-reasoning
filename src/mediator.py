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

    def analyze(self, problem: str) -> FinalAnalysis:
        # Round 1: Independent analysis
        logger.info("Starting Round 1: Independent Analysis")
        round1_outputs: List[ModuleOutput] = []
        for module in self.modules:
            try:
                output = module.run_round1(problem)
                round1_outputs.append(output)
            except Exception as e:
                logger.error("Module %s failed in Round 1: %s", module.name, e)

        # Round 2: Informed revision
        logger.info("Starting Round 2: Informed Revision")
        round1_dicts = [o.model_dump() for o in round1_outputs]
        round2_outputs: List[ModuleOutput] = []
        for module in self.modules:
            # Only run round 2 for modules that succeeded in round 1
            if not any(o.module_name == module.name for o in round1_outputs):
                continue
            try:
                output = module.run_round2(problem, round1_dicts)
                round2_outputs.append(output)
            except Exception as e:
                logger.error("Module %s failed in Round 2: %s", module.name, e)

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

        return FinalAnalysis(
            problem=problem,
            module_outputs=all_outputs,
            conflicts=synthesis_result.get("conflicts", []),
            synthesis=synthesis_result.get("synthesis", ""),
            recommendations=synthesis_result.get("recommendations", []),
            priority_flags=synthesis_result.get("priority_flags", []),
        )
