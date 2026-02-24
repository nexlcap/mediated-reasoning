from src.agents.base_agent import BaseAgent


class ScalabilityAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "scalability"
