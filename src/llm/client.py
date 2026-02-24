import json
import logging
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import litellm

# Suppress LiteLLM's own verbose output — we control logging via our logger
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)


def _with_otel_ctx(ctx, fn, *args, **kwargs):
    """Re-attach OTEL context inside a worker thread, then call fn."""
    if ctx is None:
        return fn(*args, **kwargs)
    from opentelemetry import context as otel_context
    token = otel_context.attach(ctx)
    try:
        return fn(*args, **kwargs)
    finally:
        otel_context.detach(token)

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Default model — any LiteLLM-supported model string works here.
# Examples:
#   Anthropic : claude-sonnet-4-6, claude-opus-4-6
#   OpenAI    : gpt-4o, gpt-4o-mini
#   Google    : gemini/gemini-2.5-flash, gemini/gemini-2.5-pro
#   Ollama    : ollama/llama3.3, ollama/phi4, ollama/qwen2.5:72b
#   Together  : together_ai/meta-llama/Llama-3-70b-chat-hf
DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeClient:
    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 8192, api_key: Optional[str] = None):
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key or None
        self._usage: Dict[str, int] = defaultdict(int)

    def _track(self, key_prefix: str, response) -> None:
        if hasattr(response, "usage") and response.usage:
            # LiteLLM uses OpenAI field names (prompt_tokens / completion_tokens)
            self._usage[f"{key_prefix}_input"] += response.usage.prompt_tokens or 0
            self._usage[f"{key_prefix}_output"] += response.usage.completion_tokens or 0

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

    def _raw_usage(self) -> Dict[str, int]:
        """Return a copy of the raw usage accumulator with all keys present."""
        keys = [
            "analyze_input", "analyze_output",
            "chat_input", "chat_output",
            "ptc_orchestrator_input", "ptc_orchestrator_output",
        ]
        return {k: self._usage[k] for k in keys}

    def analyze(self, system_prompt: str, user_prompt: str, repeat_prompt: bool = False, timeout: int = 120) -> Dict:
        if repeat_prompt:
            user_prompt = user_prompt + "\n\n" + user_prompt
        logger.debug("Sending request to %s", self.model)
        try:
            response = litellm.completion(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=timeout,
                **({"api_key": self._api_key} if self._api_key else {}),
            )
            self._track("analyze", response)
            text = response.choices[0].message.content
            stop_reason = getattr(response.choices[0], "finish_reason", "unknown")
            if not text:
                raise ValueError(f"Empty response from model (finish_reason={stop_reason!r})")
            logger.debug("Response text (first 200 chars): %r  finish_reason=%r", text[:200], stop_reason)
            return self._extract_json(text)
        except Exception as e:
            logger.error("API error: %s", e)
            raise

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a message and return plain text (no JSON parsing)."""
        logger.debug("Sending chat request to %s", self.model)
        try:
            response = litellm.completion(
                model=self.model,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                timeout=120,
                **({"api_key": self._api_key} if self._api_key else {}),
            )
            self._track("chat", response)
            return response.choices[0].message.content
        except Exception as e:
            logger.error("API error: %s", e)
            raise

    def run_ptc_round(
        self,
        problem: str,
        agents: list,                          # List[BaseAgent]
        round1_outputs: Optional[list] = None,  # list[dict] — None for Round 1
        searcher=None,
    ) -> list:                                  # List[AgentOutput]
        """Run one analysis round using programmatic tool calling.

        All agent analyses are dispatched in parallel by an orchestrating
        LLM call. AgentOutput objects are captured in the tool handler and
        never enter the orchestrating context.
        """
        round_num = 2 if round1_outputs is not None else 1
        agent_map = {m.name: m for m in agents}
        agent_names = [m.name for m in agents]

        # OpenAI-style function tool definition (LiteLLM normalises this
        # across all providers, including Anthropic)
        analyze_tool = {
            "type": "function",
            "function": {
                "name": "analyze_agent",
                "description": (
                    f"Run Round {round_num} analysis for one expert agent. "
                    "You MUST call this tool once for EVERY agent listed, all in the same response."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "enum": agent_names,
                            "description": "Which expert agent to run",
                        }
                    },
                    "required": ["agent_name"],
                },
            },
        }
        tools = [analyze_tool]

        agent_list = ", ".join(agent_names)
        system = (
            "You orchestrate a parallel analysis pipeline. "
            f"Call analyze_agent once for EVERY agent in a single response: {agent_list}. "
            "Do not explain or summarize — just call the tool for each agent."
        )
        user = (
            f"Run Round {round_num} analysis. "
            f"Call analyze_agent for ALL {len(agent_names)} agents: {agent_list}"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        captured: dict = {}   # agent_name -> AgentOutput

        while True:
            response = litellm.completion(
                model=self.model,
                max_tokens=512,
                messages=messages,
                tools=tools,
                timeout=60,
                **({"api_key": self._api_key} if self._api_key else {}),
            )
            self._track("ptc_orchestrator", response)

            tool_calls = response.choices[0].message.tool_calls or []

            if not tool_calls:
                break   # stop — orchestrator finished, all results captured

            # Rebuild assistant message dict with tool_calls for the next turn
            assistant_msg = {
                "role": "assistant",
                "content": response.choices[0].message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }

            # Execute all tool calls in parallel on our server
            tool_result_messages = []
            from src import observability
            current_ctx = observability.get_otel_context()
            with ThreadPoolExecutor(max_workers=len(tool_calls)) as executor:
                futures = {}
                for tc in tool_calls:
                    args = json.loads(tc.function.arguments)
                    name = args.get("agent_name")
                    agent = agent_map.get(name)
                    if not agent:
                        continue
                    if round_num == 1:
                        f = executor.submit(_with_otel_ctx, current_ctx, agent.run_round1, problem, searcher)
                    else:
                        f = executor.submit(_with_otel_ctx, current_ctx, agent.run_round2, problem, round1_outputs, searcher)
                    futures[f] = (tc.id, name)

                for f, (tc_id, name) in futures.items():
                    try:
                        output = f.result(timeout=180)
                        captured[name] = output
                        tool_result_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": "ok",
                        })
                    except Exception as e:
                        logger.error("Agent %s failed in Round %d: %s", name, round_num, e)
                        tool_result_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": f"error: {e}",
                        })

            messages = messages + [assistant_msg] + tool_result_messages

        agent_order = {m.name: i for i, m in enumerate(agents)}
        return sorted(captured.values(), key=lambda o: agent_order.get(o.agent_name, 999))

    @staticmethod
    def _extract_json(text: str) -> Dict:
        # Try to extract JSON from markdown code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            if not extracted:
                raise ValueError(f"Empty JSON block in code fence. Full response ({len(text)} chars): {text[:500]!r}")
            return json.loads(extracted)
        # Try parsing the whole text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed ({e}). Response ({len(text)} chars, finish_reason unknown): {text[:500]!r}") from e
