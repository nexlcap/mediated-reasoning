import json
import re
from typing import Dict

import anthropic

from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


class ClaudeClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.client = anthropic.Anthropic()
        self.model = model

    def analyze(self, system_prompt: str, user_prompt: str) -> Dict:
        logger.debug("Sending request to %s", self.model)
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            return self._extract_json(text)
        except anthropic.APIError as e:
            logger.error("API error: %s", e)
            raise
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse JSON from response: %s", e)
            raise

    @staticmethod
    def _extract_json(text: str) -> Dict:
        # Try to extract JSON from markdown code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try parsing the whole text as JSON
        return json.loads(text)
