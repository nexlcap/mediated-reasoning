import pytest
from unittest.mock import MagicMock, patch

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
    "sources": ["IBISWorld Food Delivery Industry Report 2024 — https://ibisworld.com/food-delivery", "McKinsey Digital Consumer Survey — https://mckinsey.com/insights/consumer-survey"],
}

SAMPLE_SYNTHESIS_RESPONSE = {
    "conflicts": [
        {
            "modules": ["market", "cost"],
            "topic": "burn rate",
            "description": "Market module sees high demand but cost module flags high burn rate",
            "severity": "high",
        }
    ],
    "synthesis": "Overall the idea has potential but requires careful financial planning.",
    "recommendations": ["Start with a single city", "Secure Series A funding"],
    "priority_flags": ["yellow: high initial investment required"],
    "sources": ["Crunchbase Funding Data 2024 — https://crunchbase.com/", "Deloitte Restaurant Industry Outlook — https://deloitte.com/insights/restaurant"],
}


def _fake_ptc_round(problem, modules, round1_outputs=None, searcher=None):
    """Fake run_ptc_round for tests: returns ModuleOutput for each module directly."""
    round_num = 2 if round1_outputs is not None else 1
    return [
        ModuleOutput(
            module_name=m.name,
            round=round_num,
            analysis=SAMPLE_LLM_RESPONSE["analysis"],
            flags=SAMPLE_LLM_RESPONSE["flags"],
            sources=SAMPLE_LLM_RESPONSE["sources"],
            revised=(round_num == 2),
        )
        for m in modules
    ]


@pytest.fixture(autouse=True)
def disable_search_prepass():
    """Prevent Tavily search from firing in unit tests."""
    with patch("src.search.searcher.SearchPrePass.run", return_value=None), \
         patch("src.search.searcher.SearchPrePass.run_for_module", return_value=None), \
         patch("src.search.searcher.SearchPrePass.run_for_conflict", return_value=None):
        yield


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
