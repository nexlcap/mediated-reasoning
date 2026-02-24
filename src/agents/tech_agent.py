from src.agents.base_agent import BaseAgent


class TechAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "tech"
