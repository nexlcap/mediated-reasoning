import json
import os
import re
from typing import Dict, List, Optional

from src.llm.client import ClaudeClient
from src.models.schemas import SearchContext, SearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SearchPrePass:
    def __init__(self, client: ClaudeClient):
        self.llm = client
        self._query_cache: Dict[str, List[SearchResult]] = {}
        self.tavily = None
        self._ddgs = None

        # Prefer Tavily when an API key is present (higher quality, paid)
        api_key = os.getenv("TAVILY_API_KEY")
        if api_key:
            try:
                from tavily import TavilyClient
                self.tavily = TavilyClient(api_key=api_key)
                logger.debug("Search backend: Tavily")
            except ImportError:
                logger.warning("TAVILY_API_KEY set but tavily-python not installed — falling back to DuckDuckGo")

        # Zero-config fallback: DuckDuckGo (no API key required)
        # Package was renamed from duckduckgo-search to ddgs; try both.
        if not self.tavily:
            try:
                from ddgs import DDGS
                self._ddgs = DDGS
                logger.debug("Search backend: DuckDuckGo (ddgs)")
            except ImportError:
                try:
                    from duckduckgo_search import DDGS
                    self._ddgs = DDGS
                    logger.debug("Search backend: DuckDuckGo (duckduckgo_search)")
                except ImportError:
                    logger.warning("No search backend available — install ddgs or set TAVILY_API_KEY")

    @property
    def _can_search(self) -> bool:
        return self.tavily is not None or self._ddgs is not None

    def run_for_module(
        self,
        problem: str,
        module_name: str,
        module_system_prompt: str,
        round_num: int = 1,
        prior_analysis: Optional[Dict] = None,
    ) -> Optional[SearchContext]:
        """Run a domain-specific search for a single module.

        Round 2 queries also incorporate the module's Round 1 findings so the
        search fetches supporting evidence and counter-arguments.
        """
        if not self._can_search:
            return None

        try:
            queries = self._generate_module_queries(
                problem, module_name, module_system_prompt, round_num, prior_analysis
            )
            if not queries:
                logger.warning("No queries generated for %s round %d", module_name, round_num)
                return None

            context = self._fetch_results(queries, cap=8)
            if context:
                logger.info(
                    "Search: %s round %d — %d results from %d queries",
                    module_name, round_num, len(context.results), len(queries),
                )
            return context

        except Exception as e:
            logger.error("Module search for %s (round %d) failed: %s", module_name, round_num, e)
            return None

    def run_for_conflict(
        self,
        problem: str,
        topic: str,
        description: str,
    ) -> Optional[SearchContext]:
        """Run targeted search to gather evidence for resolving a specific conflict or red flag."""
        if not self._can_search:
            return None
        try:
            queries = self._generate_conflict_queries(problem, topic, description)
            if not queries:
                logger.warning("No queries generated for conflict '%s'", topic)
                return None
            context = self._fetch_results(queries, cap=6)
            if context:
                logger.info(
                    "Conflict search: '%s' — %d results from %d queries",
                    topic, len(context.results), len(queries),
                )
            return context
        except Exception as e:
            logger.error("Conflict search for '%s' failed: %s", topic, e)
            return None

    def run(self, problem: str) -> Optional[SearchContext]:
        """Legacy single pre-pass (topic-level queries, not module-specific)."""
        if not self._can_search:
            logger.warning("No search backend configured — skipping search")
            return None

        try:
            queries = self._generate_queries(problem)
            if not queries:
                logger.warning("No search queries generated — skipping search")
                return None
            return self._fetch_results(queries, cap=12)
        except Exception as e:
            logger.error("Search pre-pass failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_module_queries(
        self,
        problem: str,
        module_name: str,
        module_system_prompt: str,
        round_num: int,
        prior_analysis: Optional[Dict],
    ) -> List[str]:
        domain_hint = module_system_prompt[:300] if module_system_prompt else module_name

        prior_context = ""
        if round_num == 2 and prior_analysis:
            findings = prior_analysis.get("key_findings", [])[:3]
            if findings:
                prior_context = (
                    f"\nRound 1 key findings to verify or investigate further: {findings}"
                )

        system = (
            "You are a research assistant. Generate 3-4 focused web search queries "
            "for a specific analysis module. Queries must cover BOTH the specific topic "
            "AND general domain knowledge (e.g. market data, legal frameworks, technical "
            "benchmarks, industry statistics, historical precedents) relevant to this "
            "module's perspective. Return ONLY a JSON object with a 'queries' key "
            "containing an array of query strings. No other text."
        )
        user = (
            f"Problem: {problem}\n"
            f"Module domain: {domain_hint}"
            f"{prior_context}\n"
            "Generate queries that help this module produce well-sourced analysis."
        )
        try:
            result = self.llm.analyze(system, user)
            queries = result.get("queries", [])
            if isinstance(queries, list):
                return [q for q in queries if isinstance(q, str)][:4]
            return []
        except Exception as e:
            logger.warning("Module query generation failed for %s: %s", module_name, e)
            return []

    def _generate_conflict_queries(
        self, problem: str, topic: str, description: str
    ) -> List[str]:
        system = (
            "You are a research assistant. Generate 3-4 focused web search queries "
            "to find evidence that resolves a specific conflict or validates a critical "
            "finding. Queries should seek concrete data, precedents, or expert consensus. "
            "Return ONLY a JSON object with a 'queries' key containing an array of query strings."
        )
        user = (
            f"Problem: {problem}\n"
            f"Conflict/issue topic: {topic}\n"
            f"Description: {description}\n"
            "Generate queries to find evidence that would resolve this conflict or "
            "validate/refute this critical finding."
        )
        try:
            result = self.llm.analyze(system, user)
            queries = result.get("queries", [])
            if isinstance(queries, list):
                return [q for q in queries if isinstance(q, str)][:4]
            return []
        except Exception as e:
            logger.warning("Conflict query generation failed for '%s': %s", topic, e)
            return []

    def _generate_queries(self, problem: str) -> List[str]:
        system = (
            "You are a research assistant. Generate 3-5 focused web search queries "
            "to gather factual background on the given problem. "
            "Return ONLY a JSON object with a 'queries' key containing an array of query strings. "
            "No other text."
        )
        user = f"Problem: {problem}"
        try:
            result = self.llm.analyze(system, user)
            queries = result.get("queries", [])
            if isinstance(queries, list):
                return [q for q in queries if isinstance(q, str)][:5]
            return []
        except Exception as e:
            logger.warning("Query generation failed: %s — trying fallback parse", e)
            try:
                text = self.llm.chat(system, user)
                match = re.search(r'\[.*?\]', text, re.DOTALL)
                if match:
                    queries = json.loads(match.group(0))
                    return [q for q in queries if isinstance(q, str)][:5]
            except Exception:
                pass
            return []

    def _search_one_query(self, query: str) -> List[SearchResult]:
        """Execute a single search query against the configured backend."""
        if self.tavily:
            response = self.tavily.search(
                query=query,
                max_results=3,
                search_depth="advanced",
                include_raw_content=False,
            )
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", r.get("snippet", "")),
                )
                for r in response.get("results", [])
                if r.get("url")
            ]
        elif self._ddgs:
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    content=r.get("body", ""),
                )
                for r in self._ddgs().text(query, max_results=3)
                if r.get("href")
            ]
        return []

    def _fetch_results(self, queries: List[str], cap: int = 8) -> Optional[SearchContext]:
        """Fetch search results for a list of queries, deduplicated by URL.

        Results are cached by query string for the lifetime of this instance so
        identical queries from different modules or rounds do not trigger
        redundant API calls.
        """
        seen_urls: set = set()
        results: List[SearchResult] = []
        for query in queries:
            if query in self._query_cache:
                cached = self._query_cache[query]
                logger.debug("Search cache hit: '%s' (%d results)", query, len(cached))
                query_results = cached
            else:
                query_results = []
                try:
                    query_results = self._search_one_query(query)
                except Exception as e:
                    logger.warning("Search query '%s' failed: %s", query, e)
                self._query_cache[query] = query_results

            for sr in query_results:
                if sr.url not in seen_urls:
                    seen_urls.add(sr.url)
                    results.append(sr)

        if not results:
            return None
        return SearchContext(queries=queries, results=results[:cap])
