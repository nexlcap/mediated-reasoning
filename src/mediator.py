import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src import observability
from src.llm.client import ClaudeClient
from src.llm.prompts import (
    MODULE_SYSTEM_PROMPTS,
    build_followup_prompt,
    build_gap_check_prompt,
    build_module_selection_prompt,
    build_resolution_prompt,
    build_synthesis_prompt,
)
from src.models.schemas import AdHocModule, Conflict, ConflictResolution, FinalAnalysis, ModuleOutput, RoundTiming, SearchContext, SelectionMetadata
from src.search import SearchPrePass
from src.modules import MODULE_REGISTRY
from src.modules.base_module import create_dynamic_module
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _strip_source_prefix(source: str) -> str:
    """Strip leading number prefix like '1. ' from source string."""
    return re.sub(r"^\d+\.\s*", "", source)


_URL_IN_SOURCE = re.compile(r"https?://[^\s]+")


def _extract_url_from_source(source: str) -> str:
    """Extract URL from a source string, or empty string if none."""
    m = _URL_IN_SOURCE.search(source)
    return m.group(0).rstrip(".,)\"'") if m else ""


def _remap_citations(text: str, index_map: Dict[int, int], drop_on_miss: bool = False) -> str:
    """Replace [N] citation markers with remapped global indices.

    drop_on_miss=True: citations with no mapping are removed (used for module
    outputs where a missing mapping means a skipped/invalid source).
    drop_on_miss=False (default): unknown citations are kept as-is (used for
    synthesis which already uses global indices directly).
    """
    def _replace(m):
        old_idx = int(m.group(1))
        new_idx = index_map.get(old_idx)
        if new_idx is None:
            return "" if drop_on_miss else f"[{old_idx}]"
        return f"[{new_idx}]"
    return re.sub(r"\[(\d+)\]", _replace, text)


def _remap_analysis(analysis: Dict, index_map: Dict[int, int], drop_on_miss: bool = False) -> Dict:
    """Remap citation markers in all string values of an analysis dict."""
    remapped = {}
    for key, value in analysis.items():
        if isinstance(value, str):
            remapped[key] = _remap_citations(value, index_map, drop_on_miss)
        elif isinstance(value, list):
            remapped[key] = [
                _remap_citations(v, index_map, drop_on_miss) if isinstance(v, str) else v
                for v in value
            ]
        else:
            remapped[key] = value
    return remapped


def _consolidate_sources(
    all_outputs: List[ModuleOutput], synthesis_result: Dict
) -> tuple[List[str], List[ModuleOutput], Dict]:
    """Build a global deduplicated source list and remap all inline citations.

    Returns (global_sources, remapped_outputs, remapped_synthesis_fields).
    """
    # 1. Build global source list, deduplicating by URL (preferred) then text
    global_sources: List[str] = []
    seen_text: Dict[str, int] = {}   # stripped text -> 1-based global index
    seen_url: Dict[str, int] = {}    # URL -> 1-based global index

    def _add_source(raw_source: str) -> int:
        """Add source to global list (deduplicating by URL then text). Returns 1-based index.

        Returns 0 if the source has no URL — these are likely hallucinated
        training-knowledge entries and are excluded from the global list.
        """
        stripped = _strip_source_prefix(raw_source)
        url = _extract_url_from_source(stripped)

        if not url:
            logger.debug("Dropping source without URL (likely hallucinated): %.80s", stripped)
            return 0  # sentinel: skip

        # URL match: same source already exists
        if url in seen_url:
            existing_idx = seen_url[url]
            # Upgrade to URL-bearing version if existing entry lacks URL
            if url not in global_sources[existing_idx - 1]:
                global_sources[existing_idx - 1] = stripped
            return existing_idx

        # Exact text match
        if stripped in seen_text:
            return seen_text[stripped]

        # New source
        global_sources.append(stripped)
        idx = len(global_sources)
        seen_text[stripped] = idx
        seen_url[url] = idx
        return idx

    # Collect per-output local-to-global mappings (only URL-backed sources)
    output_maps: List[Dict[int, int]] = []
    for output in all_outputs:
        index_map: Dict[int, int] = {}
        for local_idx, raw_source in enumerate(output.sources, 1):
            global_idx = _add_source(raw_source)
            if global_idx > 0:
                index_map[local_idx] = global_idx
            # local_idx absent from index_map → citation will be dropped
        output_maps.append(index_map)

    # Synthesis sources
    synthesis_map: Dict[int, int] = {}
    for local_idx, raw_source in enumerate(synthesis_result.get("sources", []), 1):
        synthesis_map[local_idx] = _add_source(raw_source)

    # 2. Remap inline citations in module outputs
    # drop_on_miss=True: citations to URL-less (skipped) or out-of-range sources are removed
    remapped_outputs = []
    for output, index_map in zip(all_outputs, output_maps):
        remapped_outputs.append(
            ModuleOutput(
                module_name=output.module_name,
                round=output.round,
                analysis=_remap_analysis(output.analysis, index_map, drop_on_miss=True),
                flags=[_remap_citations(f, index_map, drop_on_miss=True) for f in output.flags],
                sources=[],  # cleared — all sources consolidated at the end
                revised=output.revised,
            )
        )

    # 3. Remap inline citations in synthesis fields
    remapped_synthesis = {}
    remapped_synthesis["conflicts"] = [
        {**c, "description": _remap_citations(c.get("description", ""), synthesis_map)}
        for c in synthesis_result.get("conflicts", [])
        if isinstance(c, dict)
    ]
    for key in ("recommendations", "priority_flags"):
        remapped_synthesis[key] = [
            _remap_citations(item, synthesis_map)
            for item in synthesis_result.get(key, [])
        ]
    remapped_synthesis["synthesis"] = _remap_citations(
        synthesis_result.get("synthesis", ""), synthesis_map
    )

    return global_sources, remapped_outputs, remapped_synthesis


def _consolidate_resolution_sources(
    global_sources: List[str],
    resolutions: List[ConflictResolution],
) -> tuple[List[str], List[ConflictResolution]]:
    """Extend the global source list with resolution sources and remap inline citations."""
    # Rebuild seen maps from the existing global list
    global_sources = list(global_sources)
    seen_text: Dict[int, int] = {}
    seen_url: Dict[str, int] = {}
    for idx, source in enumerate(global_sources, 1):
        seen_text[source] = idx
        url = _extract_url_from_source(source)
        if url:
            seen_url[url] = idx

    def _add_source(raw_source: str) -> int:
        stripped = _strip_source_prefix(raw_source)
        url = _extract_url_from_source(stripped)
        if not url:
            logger.debug("Dropping resolution source without URL: %.80s", stripped)
            return 0  # sentinel: skip
        if url in seen_url:
            existing_idx = seen_url[url]
            if url not in global_sources[existing_idx - 1]:
                global_sources[existing_idx - 1] = stripped
            return existing_idx
        if stripped in seen_text:
            return seen_text[stripped]
        global_sources.append(stripped)
        idx = len(global_sources)
        seen_text[stripped] = idx
        seen_url[url] = idx
        return idx

    remapped = []
    for res in resolutions:
        index_map: Dict[int, int] = {}
        for local_idx, raw_source in enumerate(res.sources, 1):
            global_idx = _add_source(raw_source)
            if global_idx > 0:
                index_map[local_idx] = global_idx
        remapped.append(ConflictResolution(
            topic=res.topic,
            modules=res.modules,
            severity=res.severity,
            verdict=_remap_citations(res.verdict, index_map, drop_on_miss=True),
            updated_recommendation=_remap_citations(res.updated_recommendation, index_map, drop_on_miss=True),
            sources=[],
        ))

    return global_sources, remapped


class Mediator:
    def __init__(
        self,
        client: ClaudeClient,
        weights: Optional[Dict[str, float]] = None,
        raci: Optional[Dict] = None,
        auto_select: bool = False,
        search: bool = True,
        deep_research: bool = False,
        module_client: Optional[ClaudeClient] = None,
        repeat_prompt: bool = True,
    ):
        self.client = client                              # synthesis + auto-select + gap-check
        self.module_client = module_client or client     # module analysis + search queries
        self.weights = weights or {}
        self.raci = raci
        self.auto_select = auto_select
        self.search = search
        self.deep_research = deep_research
        self.repeat_prompt = repeat_prompt
        self.selection_metadata: Optional[SelectionMetadata] = None

        if not auto_select:
            self._init_default_modules()

    def _init_default_modules(self):
        all_modules = [cls(self.module_client) for cls in MODULE_REGISTRY]
        self.deactivated_modules = [
            m.name for m in all_modules if self.weights.get(m.name, 1) == 0
        ]
        self.modules = [
            m for m in all_modules if m.name not in self.deactivated_modules
        ]

    def _select_modules(self, problem: str) -> None:
        """Run the two-step LLM pre-pass: module selection + gap check."""
        registry_by_name = {cls(None).name: cls for cls in MODULE_REGISTRY}

        try:
            # Step 1: Module selection
            system, user = build_module_selection_prompt(problem)
            selection_result = self.client.analyze(system, user, repeat_prompt=self.repeat_prompt)
            selected_names = selection_result.get("selected_modules", [])
            selection_reasoning = selection_result.get("reasoning", "")

            # Validate against known modules
            selected_names = [
                n for n in selected_names if n in MODULE_SYSTEM_PROMPTS
            ]
            if not selected_names:
                logger.warning("Auto-select returned no valid modules, falling back to defaults")
                self._init_default_modules()
                return

            # Step 2: Gap check
            system, user = build_gap_check_prompt(problem, selected_names)
            gap_result = self.client.analyze(system, user, repeat_prompt=self.repeat_prompt)
            gap_reasoning = gap_result.get("reasoning", "")
            raw_ad_hoc = gap_result.get("ad_hoc_modules", [])

            # Cap ad-hoc at 3, skip name collisions
            existing_names = set(MODULE_SYSTEM_PROMPTS.keys()) | set(selected_names)
            ad_hoc_modules: List[AdHocModule] = []
            for item in raw_ad_hoc[:3]:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", "")
                prompt = item.get("system_prompt", "")
                if not name or not prompt:
                    continue
                if name in existing_names:
                    continue
                ad_hoc_modules.append(AdHocModule(name=name, system_prompt=prompt))
                existing_names.add(name)

            # Instantiate selected modules
            modules = []
            for name in selected_names:
                if name in registry_by_name:
                    modules.append(registry_by_name[name](self.module_client))
                else:
                    modules.append(
                        create_dynamic_module(name, MODULE_SYSTEM_PROMPTS[name], self.module_client)
                    )

            # Instantiate ad-hoc modules
            for adhoc in ad_hoc_modules:
                modules.append(
                    create_dynamic_module(adhoc.name, adhoc.system_prompt, self.module_client)
                )

            # Apply weight=0 deactivation
            self.deactivated_modules = [
                m.name for m in modules if self.weights.get(m.name, 1) == 0
            ]
            self.modules = [
                m for m in modules if m.name not in self.deactivated_modules
            ]

            self.selection_metadata = SelectionMetadata(
                auto_selected=True,
                selected_modules=[m.name for m in self.modules],
                selection_reasoning=selection_reasoning,
                gap_check_reasoning=gap_reasoning,
                ad_hoc_modules=ad_hoc_modules,
            )

        except Exception as e:
            logger.error("Auto-select failed (%s), falling back to defaults", e)
            self._init_default_modules()

    def _run_deep_research(
        self,
        problem: str,
        conflicts: List[Conflict],
        priority_flags: List[str],
        module_outputs: List[ModuleOutput],
        searcher,
    ) -> List[ConflictResolution]:
        """Run targeted research for high/critical conflicts and red flags."""

        def _get_position(module_name: str) -> str:
            r2 = next((o for o in module_outputs if o.module_name == module_name and o.round == 2), None)
            r1 = next((o for o in module_outputs if o.module_name == module_name and o.round == 1), None)
            output = r2 or r1
            if not output:
                return ""
            summary = output.analysis.get("summary", "")
            flags_text = "; ".join(output.flags[:3])
            return f"Summary: {summary}\nTop flags: {flags_text}"

        # Collect items to research
        items: List[Dict] = []
        processed_topics: set = set()

        for conflict in conflicts:
            if conflict.severity in ("high", "critical"):
                items.append({
                    "topic": conflict.topic,
                    "description": conflict.description,
                    "modules": conflict.modules,
                    "severity": conflict.severity,
                })
                processed_topics.add(conflict.topic.lower())

        for flag in priority_flags:
            if not flag.lower().startswith("red:"):
                continue
            flag_text = flag[len("red:"):].strip()
            # Skip if a conflict already covers this flag
            if any(t in flag_text.lower() for t in processed_topics):
                continue
            items.append({
                "topic": flag_text[:80],
                "description": flag_text,
                "modules": [],
                "severity": "red",
            })

        if not items:
            logger.info("Deep research: no high/critical conflicts or red flags to research")
            return []

        logger.info("Deep research: researching %d items", len(items))

        def resolve_item(item: Dict) -> Optional[ConflictResolution]:
            topic = item["topic"]
            description = item["description"]
            modules = item["modules"]
            severity = item["severity"]

            search_context = None
            if searcher:
                search_context = searcher.run_for_conflict(problem, topic, description)

            module_positions = {m: _get_position(m) for m in modules}
            system, user = build_resolution_prompt(
                problem, topic, description, modules, module_positions, search_context
            )
            try:
                result = self.client.analyze(system, user)
                return ConflictResolution(
                    topic=topic,
                    modules=modules,
                    severity=severity,
                    verdict=result.get("verdict", ""),
                    updated_recommendation=result.get("updated_recommendation", ""),
                    sources=result.get("sources", []),
                )
            except Exception as e:
                logger.error("Resolution for '%s' failed: %s", topic, e)
                return None

        results: List[ConflictResolution] = []
        with ThreadPoolExecutor(max_workers=min(len(items), 5)) as executor:
            future_to_item = {executor.submit(resolve_item, item): item for item in items}
            for future in as_completed(future_to_item):
                result = future.result()
                if result:
                    results.append(result)

        # Restore original order
        topic_order = {item["topic"]: i for i, item in enumerate(items)}
        results.sort(key=lambda r: topic_order.get(r.topic, 999))
        return results

    def _merge_token_usage(self) -> "TokenUsage":
        from src.models.schemas import TokenUsage
        if self.module_client is self.client:
            return self.client.token_usage()
        m = self.module_client._raw_usage()
        s = self.client._raw_usage()
        ai = m["analyze_input"] + s["analyze_input"]
        ao = m["analyze_output"] + s["analyze_output"]
        ci = s["chat_input"]
        co = s["chat_output"]
        pi = s["ptc_orchestrator_input"]
        po = s["ptc_orchestrator_output"]
        return TokenUsage(
            analyze_input=ai,
            analyze_output=ao,
            module_analyze_input=m["analyze_input"],
            module_analyze_output=m["analyze_output"],
            synthesis_analyze_input=s["analyze_input"],
            synthesis_analyze_output=s["analyze_output"],
            chat_input=ci,
            chat_output=co,
            ptc_orchestrator_input=pi,
            ptc_orchestrator_output=po,
            total_input=ai + ci + pi,
            total_output=ao + co + po,
        )

    def analyze(self, problem: str) -> FinalAnalysis:
        if self.auto_select:
            with observability.span("auto-select"):
                self._select_modules(problem)
        else:
            pass  # modules already initialized in __init__

        # Create searcher once; uses module_client for query generation
        searcher = SearchPrePass(self.module_client) if self.search else None

        t_start = time.perf_counter()

        # Round 1: Independent analysis (all modules dispatched in parallel via PTC)
        logger.info("Starting Round 1: Independent Analysis")
        round1_outputs: List[ModuleOutput] = []
        with observability.span("round-1"):
            try:
                round1_outputs = self.client.run_ptc_round(
                    problem, self.modules, searcher=searcher
                )
            except Exception as e:
                logger.error("Round 1 failed: %s", e)
        module_order = {m.name: i for i, m in enumerate(self.modules)}
        round1_outputs.sort(key=lambda o: module_order[o.module_name])

        t1 = time.perf_counter()

        # Round 2: Informed revision (all eligible modules dispatched in parallel via PTC)
        logger.info("Starting Round 2: Informed Revision")
        round1_dicts = [o.model_dump() for o in round1_outputs]
        round1_names = {o.module_name for o in round1_outputs}
        eligible_modules = [m for m in self.modules if m.name in round1_names]
        round2_outputs: List[ModuleOutput] = []
        with observability.span("round-2"):
            if eligible_modules:
                try:
                    round2_outputs = self.client.run_ptc_round(
                        problem, eligible_modules, round1_outputs=round1_dicts, searcher=searcher
                    )
                except Exception as e:
                    logger.error("Round 2 failed: %s", e)
        round2_outputs.sort(key=lambda o: module_order[o.module_name])

        t2 = time.perf_counter()

        # Capture sources_claimed BEFORE _consolidate_sources deduplicates/filters them
        all_outputs = round1_outputs + round2_outputs
        sources_claimed = sum(len(o.sources) for o in all_outputs)

        # Round 3: Synthesis
        logger.info("Starting Round 3: Synthesis")

        synthesis_result = {}
        with observability.span("synthesis"):
            if all_outputs:
                # Pre-consolidate module sources so synthesis can cite real [N] numbers
                pre_global_sources, pre_remapped_outputs, _ = _consolidate_sources(
                    all_outputs, {}
                )
                all_output_dicts = [o.model_dump() for o in pre_remapped_outputs]
                system, user = build_synthesis_prompt(
                    problem, all_output_dicts,
                    weights=self.weights,
                    deactivated_modules=self.deactivated_modules,
                    raci=self.raci,
                    global_sources=pre_global_sources,
                )
                try:
                    synthesis_result = self.client.analyze(system, user, repeat_prompt=self.repeat_prompt)
                except Exception as e:
                    logger.error("Synthesis failed: %s", e)
            else:
                logger.error("All modules failed — no data to synthesize")

        t3 = time.perf_counter()

        # Final consolidation: remap all inline citations consistently
        global_sources, remapped_outputs, remapped_synthesis = (
            _consolidate_sources(all_outputs, synthesis_result)
        )

        conflicts = [Conflict(**c) for c in remapped_synthesis["conflicts"]]
        priority_flags = remapped_synthesis["priority_flags"]

        # Optional deep research round: targeted search on high/critical conflicts + red flags
        conflict_resolutions: List[ConflictResolution] = []
        if self.deep_research:
            logger.info("Starting Deep Research Round: Conflict & Flag Resolution")
            with observability.span("deep-research"):
                conflict_resolutions = self._run_deep_research(
                    problem, conflicts, priority_flags, remapped_outputs, searcher
                )
            if conflict_resolutions:
                global_sources, conflict_resolutions = _consolidate_resolution_sources(
                    global_sources, conflict_resolutions
                )

        token_usage = self._merge_token_usage()

        result = FinalAnalysis(
            problem=problem,
            generated_at=datetime.now(timezone.utc).isoformat(),
            module_outputs=remapped_outputs,
            conflicts=conflicts,
            synthesis=remapped_synthesis["synthesis"],
            recommendations=remapped_synthesis["recommendations"],
            priority_flags=priority_flags,
            sources=global_sources,
            deactivated_disclaimer=synthesis_result.get("deactivated_disclaimer", ""),
            raci_matrix=self.raci or {},
            selection_metadata=self.selection_metadata,
            weights=self.weights,
            search_enabled=self.search,
            conflict_resolutions=conflict_resolutions,
            deep_research_enabled=self.deep_research,
            module_model=self.module_client.model if self.module_client is not self.client else "",
            token_usage=token_usage,
            timing=RoundTiming(
                round1_s=round(t1 - t_start, 2),
                round2_s=round(t2 - t1, 2),
                round3_s=round(t3 - t2, 2),
                total_s=round(t3 - t_start, 2),
            ),
            modules_attempted=len(self.modules),
            modules_completed=len(round1_outputs),
            sources_claimed=sources_claimed,
        )

        from src.audit.quality_gate import evaluate
        result.quality = evaluate(result)
        if result.quality.tier != "good":
            logger.warning(
                "Run quality: %s (score %.2f) — %s",
                result.quality.tier,
                result.quality.score,
                "; ".join(result.quality.warnings),
            )

        return result

    def followup(self, analysis: FinalAnalysis, question: str) -> str:
        system, user = build_followup_prompt(analysis.problem, analysis, question)
        return self.client.chat(system, user)
