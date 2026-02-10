from abc import ABC, abstractmethod
from typing import Dict, List

from src.llm.client import ClaudeClient
from src.llm.prompts import build_round1_prompt, build_round2_prompt
from src.models.schemas import ModuleOutput
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BaseModule(ABC):
    def __init__(self, client: ClaudeClient):
        self.client = client

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    def run_round1(self, problem: str) -> ModuleOutput:
        logger.info("Running %s module - Round 1", self.name)
        system, user = build_round1_prompt(self.name, problem)
        result = self.client.analyze(system, user)
        return ModuleOutput(
            module_name=self.name,
            round=1,
            analysis=result.get("analysis", result),
            flags=result.get("flags", []),
            sources=result.get("sources", []),
            revised=False,
        )

    def run_round2(
        self, problem: str, round1_outputs: List[Dict]
    ) -> ModuleOutput:
        logger.info("Running %s module - Round 2", self.name)
        system, user = build_round2_prompt(self.name, problem, round1_outputs)
        result = self.client.analyze(system, user)
        return ModuleOutput(
            module_name=self.name,
            round=2,
            analysis=result.get("analysis", result),
            flags=result.get("flags", []),
            sources=result.get("sources", []),
            revised=True,
        )
