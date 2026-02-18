"""
Layer 4: Grounding verifier.

Samples cited claims from the report, fetches each cited source, and asks the
LLM whether the source actually supports the claim.  Verdict per claim:
SUPPORTED / PARTIAL / UNSUPPORTED / FETCH_FAILED / ERROR.
"""
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import httpx

from src.models.schemas import FinalAnalysis
from src.llm.client import ClaudeClient

_URL_RE = re.compile(r'https://\S+')
_CITE_RE = re.compile(r'\[(\d+)\]')


def _collect_cited_sentences(analysis: FinalAnalysis) -> List[Dict]:
    """Return list of {sentence, citation_index} pairs."""
    parts = [analysis.synthesis]
    parts.extend(analysis.recommendations)
    for mo in analysis.module_outputs:
        if isinstance(mo.analysis, dict):
            parts.append(json.dumps(mo.analysis))
        else:
            parts.append(str(mo.analysis))
    for res in analysis.conflict_resolutions:
        parts.append(res.verdict)

    all_text = " ".join(parts)
    sentences = re.split(r'(?<=[.!?])\s+', all_text)

    pairs = []
    for sentence in sentences:
        for m in _CITE_RE.finditer(sentence):
            pairs.append({"sentence": sentence.strip(), "citation": int(m.group(1))})
    return pairs


def _fetch_source_text(url: str, timeout: int = 10) -> Optional[str]:
    try:
        r = httpx.get(url, follow_redirects=True, timeout=timeout,
                      headers={"User-Agent": "Mozilla/5.0 (audit/1.0)"})
        if r.status_code >= 400:
            return None
        # Strip HTML tags and collapse whitespace
        text = re.sub(r'<[^>]+>', ' ', r.text)
        text = re.sub(r'\s+', ' ', text)
        return text[:4000]
    except Exception:
        return None


def _check_grounding(client: ClaudeClient, claim: str, source_text: str) -> str:
    system = (
        "You are a rigorous fact-checker. Given a claim and an excerpt from a source "
        "document, decide whether the source supports the claim. "
        "Reply with exactly one word: SUPPORTED, PARTIAL, or UNSUPPORTED. "
        "No explanation."
    )
    user = f"Claim: {claim}\n\nSource excerpt:\n{source_text}"
    try:
        # Use chat() since we want a plain-text one-word response
        result = client.chat(system, user).strip().upper()
        for verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED"):
            if verdict in result:
                return verdict
        return "UNKNOWN"
    except Exception as e:
        return f"ERROR: {e}"


def verify_grounding(
    analysis: FinalAnalysis,
    sample_rate: float = 0.2,
    client: Optional[ClaudeClient] = None,
    max_workers: int = 5,
) -> List[Dict]:
    """
    Returns list of {sentence, citation, url, verdict} dicts for each sampled claim.
    """
    if client is None:
        client = ClaudeClient(model="claude-haiku-4-5-20251001")

    pairs = _collect_cited_sentences(analysis)
    if not pairs:
        return []

    # Sample
    sample_size = max(1, int(len(pairs) * sample_rate))
    sample = random.sample(pairs, min(sample_size, len(pairs)))

    # Build (sentence, citation_idx, url) triples
    triples = []
    for item in sample:
        idx = item["citation"]
        if idx < 1 or idx > len(analysis.sources):
            continue
        source = analysis.sources[idx - 1]
        m = _URL_RE.search(source)
        if not m:
            continue
        from src.audit.url_checker import _clean_url
        url = _clean_url(m.group())
        triples.append((item["sentence"], idx, url))

    if not triples:
        return []

    # Fetch sources in parallel, then call LLM sequentially (avoid rate-limiting)
    fetched: Dict[str, Optional[str]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_source_text, url): url
                   for _, _, url in triples}
        for future in as_completed(futures):
            url = futures[future]
            fetched[url] = future.result()

    results = []
    for sentence, citation_idx, url in triples:
        source_text = fetched.get(url)
        if source_text is None:
            verdict = "FETCH_FAILED"
        else:
            verdict = _check_grounding(client, sentence, source_text)
        results.append({
            "sentence": sentence,
            "citation": citation_idx,
            "url": url,
            "verdict": verdict,
        })

    return results


def main(args: List[str] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Verify that cited sources support the claims that cite them"
    )
    parser.add_argument("report", help="Path to report.json")
    parser.add_argument("--sample-rate", type=float, default=0.2,
                        help="Fraction of citations to check (default: 0.2)")
    parsed = parser.parse_args(args)

    with open(parsed.report) as f:
        analysis = FinalAnalysis(**json.load(f))

    print(f"Verifying grounding (sample rate: {parsed.sample_rate:.0%})...")
    results = verify_grounding(analysis, sample_rate=parsed.sample_rate)

    if not results:
        print("No cited sentences found.")
        return 0

    by_verdict: Dict[str, List[Dict]] = {}
    for r in results:
        by_verdict.setdefault(r["verdict"], []).append(r)

    markers = {"SUPPORTED": "✓", "PARTIAL": "~", "UNSUPPORTED": "✗",
               "FETCH_FAILED": "?", "UNKNOWN": "?"}

    exit_code = 0
    for verdict in ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "FETCH_FAILED", "UNKNOWN"):
        items = by_verdict.get(verdict, [])
        if not items:
            continue
        m = markers.get(verdict, "?")
        print(f"\n{m} {verdict} ({len(items)})")
        if verdict != "SUPPORTED":
            exit_code = 1
            for item in items:
                print(f"  [{item['citation']}] {item['sentence'][:120]}...")
                print(f"       {item['url']}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
