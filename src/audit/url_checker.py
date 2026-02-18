"""
Layer 3: URL reachability check.

Extracts every https:// URL from sources and resolution sources, then issues
HTTP HEAD requests in parallel to verify each is reachable (2xx/3xx).
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import httpx

from src.models.schemas import FinalAnalysis

_URL_RE = re.compile(r'https://\S+')


def _extract_urls(analysis: FinalAnalysis) -> List[str]:
    """Return deduplicated list of URLs from all source fields."""
    urls = []
    seen = set()

    def _add(source: str) -> None:
        m = _URL_RE.search(source)
        if m:
            url = m.group().rstrip(".,)")
            if url not in seen:
                seen.add(url)
                urls.append(url)

    for s in analysis.sources:
        _add(s)
    for res in analysis.conflict_resolutions:
        for s in res.sources:
            _add(s)

    return urls


def _check_url(url: str, timeout: int) -> Dict:
    try:
        r = httpx.head(url, follow_redirects=True, timeout=timeout,
                       headers={"User-Agent": "Mozilla/5.0 (audit/1.0)"})
        ok = r.status_code < 400
        return {"url": url, "status": r.status_code, "error": None, "ok": ok}
    except httpx.TimeoutException:
        return {"url": url, "status": None, "error": "timeout", "ok": False}
    except Exception as e:
        return {"url": url, "status": None, "error": str(e), "ok": False}


def check_urls(analysis: FinalAnalysis, timeout: int = 8,
               max_workers: int = 10) -> List[Dict]:
    """Return list of result dicts (url, status, error, ok)."""
    urls = _extract_urls(analysis)
    if not urls:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_check_url, url, timeout): url for url in urls}
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: r["url"])
    return results


def main(args: List[str] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Check URL reachability for report sources")
    parser.add_argument("report", help="Path to report.json")
    parser.add_argument("--timeout", type=int, default=8, help="Per-URL timeout in seconds")
    parsed = parser.parse_args(args)

    with open(parsed.report) as f:
        analysis = FinalAnalysis(**json.load(f))

    print(f"Checking {len(_extract_urls(analysis))} URLs...")
    results = check_urls(analysis, timeout=parsed.timeout)

    ok = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]

    print(f"Reachable: {len(ok)}/{len(results)}")

    if failures:
        print("\nFAILURES:")
        for r in failures:
            status = r["status"] or "ERR"
            detail = r["error"] or ""
            print(f"  [{status}] {r['url']}  {detail}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
