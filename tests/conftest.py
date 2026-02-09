import pytest
from unittest.mock import MagicMock

from src.llm.client import ClaudeClient
from src.models.schemas import ModuleOutput


SAMPLE_PROBLEM = "I want to build a food delivery app"

SAMPLE_LLM_RESPONSE = {
    "analysis": {
        "summary": "Test summary",
        "key_findings": ["finding 1"],
        "opportunities": ["opportunity 1"],
        "risks": ["risk 1"],
    },
    "flags": ["green: looks good", "yellow: some caution"],
}

SAMPLE_SYNTHESIS_RESPONSE = {
    "conflicts": ["Market module sees high demand but cost module flags high burn rate"],
    "synthesis": "Overall the idea has potential but requires careful financial planning.",
    "recommendations": ["Start with a single city", "Secure Series A funding"],
    "priority_flags": ["yellow: high initial investment required"],
}


@pytest.fixture
def mock_client():
    client = MagicMock(spec=ClaudeClient)
    client.analyze.return_value = SAMPLE_LLM_RESPONSE
    return client


@pytest.fixture
def sample_problem():
    return SAMPLE_PROBLEM


@pytest.fixture
def sample_module_output():
    return ModuleOutput(
        module_name="market",
        round=1,
        analysis=SAMPLE_LLM_RESPONSE["analysis"],
        flags=SAMPLE_LLM_RESPONSE["flags"],
        revised=False,
    )
