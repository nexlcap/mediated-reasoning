from src.agents.base_agent import BaseAgent


class CostAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "cost"
