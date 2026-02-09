from src.modules.base_module import BaseModule


class CostModule(BaseModule):
    @property
    def name(self) -> str:
        return "cost"
