from src.agents.base_agent import BaseAgent


class MarketAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "market"
