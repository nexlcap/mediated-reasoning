from src.agents.base_agent import BaseAgent


class RiskAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "risk"
