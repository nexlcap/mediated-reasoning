import json
import re
from collections import defaultdict
from typing import Dict

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

    @staticmethod
    def _extract_json(text: str) -> Dict:
        # Try to extract JSON from markdown code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try parsing the whole text as JSON
        return json.loads(text)
