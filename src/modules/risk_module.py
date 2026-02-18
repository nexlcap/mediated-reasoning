from src.modules.base_module import BaseModule


class RiskModule(BaseModule):
    @property
    def name(self) -> str:
        return "risk"
