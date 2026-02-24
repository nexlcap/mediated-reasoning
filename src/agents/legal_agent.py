from src.agents.base_agent import BaseAgent


class LegalAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "legal"
