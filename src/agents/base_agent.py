from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.llm.client import ClaudeClient
from src.llm.prompts import AGENT_SYSTEM_PROMPTS, build_round1_prompt, build_round2_prompt
from src.models.schemas import AgentOutput
from src.utils.logger import get_logger

logger = get_logger(__name__)


def create_dynamic_agent(name: str, system_prompt: str, client: ClaudeClient) -> "BaseAgent":
    """Create a BaseAgent subclass on-the-fly with the given name and system prompt."""
    AGENT_SYSTEM_PROMPTS[name] = system_prompt

    cls = type(
        f"DynamicAgent_{name}",
        (BaseAgent,),
        {"name": property(lambda self, _name=name: _name)},
    )
    return cls(client)


class BaseAgent(ABC):
    def __init__(self, client: ClaudeClient):
        self.client = client

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    def run_round1(self, problem: str, searcher=None) -> AgentOutput:
        logger.info("Running %s agent - Round 1", self.name)
        search_context = None
        if searcher:
            search_context = searcher.run_for_agent(
                problem,
                self.name,
                AGENT_SYSTEM_PROMPTS.get(self.name, ""),
                round_num=1,
            )
        system, user = build_round1_prompt(self.name, problem, search_context)
        result = self.client.analyze(system, user)
        return AgentOutput(
            agent_name=self.name,
            round=1,
            analysis=result.get("analysis", result),
            flags=result.get("flags", []),
            sources=result.get("sources", []),
            revised=False,
        )

    def run_round2(
        self, problem: str, round1_outputs: List[Dict], searcher=None
    ) -> AgentOutput:
        logger.info("Running %s agent - Round 2", self.name)
        my_r1 = next((o for o in round1_outputs if o["agent_name"] == self.name), None)
        prior_analysis = my_r1.get("analysis") if my_r1 else None
        search_context = None
        if searcher:
            search_context = searcher.run_for_agent(
                problem,
                self.name,
                AGENT_SYSTEM_PROMPTS.get(self.name, ""),
                round_num=2,
                prior_analysis=prior_analysis,
            )
        system, user = build_round2_prompt(self.name, problem, round1_outputs, search_context)
        result = self.client.analyze(system, user)
        return AgentOutput(
            agent_name=self.name,
            round=2,
            analysis=result.get("analysis", result),
            flags=result.get("flags", []),
            sources=result.get("sources", []),
            revised=True,
        )
