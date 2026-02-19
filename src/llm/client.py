import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import anthropic

from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.client = anthropic.Anthropic()
        self.model = model
        self._usage: Dict[str, int] = defaultdict(int)

    def _track(self, key_prefix: str, response) -> None:
        if hasattr(response, "usage") and response.usage:
            self._usage[f"{key_prefix}_input"] += response.usage.input_tokens
            self._usage[f"{key_prefix}_output"] += response.usage.output_tokens

    def token_usage(self) -> "TokenUsage":
        from src.models.schemas import TokenUsage
        u = self._usage
        ti = u["analyze_input"] + u["chat_input"] + u["ptc_orchestrator_input"]
        to = u["analyze_output"] + u["chat_output"] + u["ptc_orchestrator_output"]
        return TokenUsage(
            analyze_input=u["analyze_input"],
            analyze_output=u["analyze_output"],
            chat_input=u["chat_input"],
            chat_output=u["chat_output"],
            ptc_orchestrator_input=u["ptc_orchestrator_input"],
            ptc_orchestrator_output=u["ptc_orchestrator_output"],
            total_input=ti,
            total_output=to,
        )

    def analyze(self, system_prompt: str, user_prompt: str) -> Dict:
        logger.debug("Sending request to %s", self.model)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            self._track("analyze", response)
            text = response.content[0].text
            return self._extract_json(text)
        except anthropic.APIError as e:
            logger.error("API error: %s", e)
            raise
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse JSON from response: %s", e)
            raise

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a message and return plain text (no JSON parsing)."""
        logger.debug("Sending chat request to %s", self.model)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            self._track("chat", response)
            return response.content[0].text
        except anthropic.APIError as e:
            logger.error("API error: %s", e)
            raise

    def run_ptc_round(
        self,
        problem: str,
        modules: list,                          # List[BaseModule]
        round1_outputs: Optional[list] = None,  # list[dict] — None for Round 1
        searcher=None,
    ) -> list:                                  # List[ModuleOutput]
        """Run one analysis round using programmatic tool calling.

        All module analyses are dispatched in parallel by an orchestrating
        Claude code execution block. ModuleOutput objects are captured in the
        tool handler and never enter the orchestrating context.
        """
        round_num = 2 if round1_outputs is not None else 1
        module_map = {m.name: m for m in modules}
        module_names = [m.name for m in modules]

        analyze_tool = {
            "name": "analyze_module",
            "description": (
                f"Run Round {round_num} analysis for one expert module. "
                "Call every module in parallel using asyncio.gather()."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "module_name": {
                        "type": "string",
                        "enum": module_names,
                        "description": "Which expert module to run",
                    }
                },
                "required": ["module_name"],
            },
            "allowed_callers": ["code_execution_20250825"],
        }
        tools = [{"type": "code_execution_20250825", "name": "code_execution"}, analyze_tool]

        system = (
            "You orchestrate a parallel analysis pipeline. "
            "Use code execution to call analyze_module() for EVERY module "
            "in parallel using asyncio.gather(). After all calls complete, print 'done'."
        )
        module_args = ", ".join(f'analyze_module("{n}")' for n in module_names)
        user = (
            f"Run Round {round_num} — call all modules in parallel.\n\n"
            f"Problem: {problem}\n\n"
            f"Call: await asyncio.gather({module_args})"
        )

        messages = [{"role": "user", "content": user}]
        captured: dict = {}   # module_name -> ModuleOutput
        container_id = None

        while True:
            kwargs = dict(
                model=self.model,
                max_tokens=512,
                system=system,
                messages=messages,
                tools=tools,
            )
            if container_id:
                kwargs["container"] = container_id

            response = self.client.messages.create(**kwargs)
            self._track("ptc_orchestrator", response)

            if getattr(response, "container", None):
                container_id = response.container.id

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                break   # end_turn — code finished, all results captured

            # Execute all tool calls in parallel on our server
            tool_results = []
            with ThreadPoolExecutor(max_workers=len(tool_uses)) as executor:
                futures = {}
                for tu in tool_uses:
                    name = tu.input.get("module_name")
                    module = module_map.get(name)
                    if not module:
                        continue
                    if round_num == 1:
                        f = executor.submit(module.run_round1, problem, searcher)
                    else:
                        f = executor.submit(module.run_round2, problem, round1_outputs, searcher)
                    futures[f] = (tu.id, name)

                for f, (tu_id, name) in futures.items():
                    try:
                        output = f.result()
                        captured[name] = output
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu_id,
                            "content": "ok",
                        })
                    except Exception as e:
                        logger.error("Module %s failed in Round %d: %s", name, round_num, e)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu_id,
                            "content": f"error: {e}",
                            "is_error": True,
                        })

            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": tool_results},
            ]

        module_order = {m.name: i for i, m in enumerate(modules)}
        return sorted(captured.values(), key=lambda o: module_order.get(o.module_name, 999))

    @staticmethod
    def _extract_json(text: str) -> Dict:
        # Try to extract JSON from markdown code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try parsing the whole text as JSON
        return json.loads(text)
