"""
Semantic HTML report generator for FinalAnalysis objects.

Generates clean, readable HTML directly from the data model — no terminal
escape codes, no <pre> blocks, no long unwrapped lines.
"""
import html
import re
from datetime import datetime, timezone
from typing import List

from src.models.schemas import Conflict, ConflictResolution, FinalAnalysis, ModuleOutput

_CITE_RE = re.compile(r"\[(\d+)\]")
_URL_RE = re.compile(r"(https?://[^\s<>&\"]+)")

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 880px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  line-height: 1.7;
  color: #1a1a1a;
  background: #fff;
}
h1 { font-size: 1.55rem; border-bottom: 2px solid #ddd; padding-bottom: .4rem; margin-bottom: .3rem; }
.meta { font-size: .82rem; color: #888; margin: .2rem 0 .6rem; }
.subtitle { font-size: .9rem; color: #777; margin: 0 0 .4rem; font-style: italic; }
h2 { font-size: 1.15rem; margin: 2.2rem 0 .7rem; color: #111; border-bottom: 1px solid #eee; padding-bottom: .2rem; scroll-margin-top: 1rem; }
h3 { font-size: 1rem; margin: 1.4rem 0 .4rem; color: #333; }
p  { margin: .5rem 0; }
a  { color: #1a5ba6; word-break: break-all; }
a.cite { text-decoration: none; color: #555; font-size: .85em; }
a.cite:hover { text-decoration: underline; }

/* ── Table of contents ──────────────────────────────────── */
nav.toc {
  background: #f8f8f8; border: 1px solid #e0e0e0;
  border-radius: 6px; padding: .8rem 1.2rem;
  margin: 1rem 0 1.5rem; font-size: .88rem;
}
nav.toc strong { display: block; font-size: .78rem; text-transform: uppercase;
  letter-spacing: .06em; color: #777; margin-bottom: .4rem; }
nav.toc ol { margin: 0; padding-left: 1.4rem; column-count: 2; column-gap: 2rem; }
nav.toc li { margin-bottom: .15rem; }
nav.toc a { color: #1a5ba6; text-decoration: none; }
nav.toc a:hover { text-decoration: underline; }

/* ── Config box ─────────────────────────────────────────── */
.config-box {
  background: #f8f8f8;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 1rem 1.25rem;
  font-size: .88rem;
  margin-bottom: 1.5rem;
}
.config-label {
  font-weight: 700; font-size: .78rem; text-transform: uppercase;
  letter-spacing: .06em; color: #777; margin-bottom: .4rem;
}
.config-cols {
  display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: .9rem;
}
.config-cols > div { flex: 1; min-width: 160px; }
.config-cols table { border-collapse: collapse; }
.config-cols td { padding: .15rem .4rem; vertical-align: top; }
.config-cols td:first-child {
  font-weight: 600; color: #555; white-space: nowrap;
  width: 1%; padding-right: 1.2rem;
}
table.weights { border-collapse: collapse; width: 100%; }
table.weights th, table.weights td { border: 1px solid #e0e0e0; padding: .25rem .55rem; text-align: left; }
table.weights th { background: #efefef; font-weight: 600; font-size: .82rem; }

/* ── Flags ──────────────────────────────────────────────── */
ul.flags { list-style: none; padding: 0; margin: .5rem 0 1rem; }
ul.flags li { padding: .25rem 0 .25rem 1.4rem; position: relative; }
ul.flags li::before { position: absolute; left: 0; font-weight: 700; }
.flag-red   { color: #b52a2a; }
.flag-red::before   { content: "●"; color: #b52a2a; }
.flag-yellow { color: #8a6000; }
.flag-yellow::before { content: "●"; color: #c47d00; }
.flag-green { color: #1e7c3a; }
.flag-green::before { content: "●"; color: #1e7c3a; }

/* ── Conflicts ──────────────────────────────────────────── */
.conflict {
  border-left: 4px solid #ccc;
  padding: .5rem 1rem;
  margin: .6rem 0;
  border-radius: 0 4px 4px 0;
}
.conflict.high, .conflict.critical { border-color: #b52a2a; }
.conflict.medium { border-color: #c47d00; }
.conflict.low    { border-color: #1e7c3a; }
.conflict-arbitration { margin-top: .35rem; font-size: .88rem; color: #555; }
.conflict-arbitration strong { color: #333; }
.conflict-label {
  font-size: .78rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .05em; margin-bottom: .25rem;
}
.conflict.high .conflict-label,
.conflict.critical .conflict-label { color: #b52a2a; }
.conflict.medium .conflict-label   { color: #8a6000; }

/* ── Deep research resolutions ──────────────────────────── */
.resolution {
  background: #f4f8fe;
  border: 1px solid #b8d0eb;
  border-radius: 6px;
  padding: 1rem 1.25rem;
  margin: .75rem 0;
}
.resolution-label {
  font-weight: 700; font-size: .85rem;
  color: #1a4a7a; margin-bottom: .5rem;
}
.resolution-verdict, .resolution-rec { margin: .4rem 0; }
.resolution-rec { font-style: italic; }

/* ── Module detail ──────────────────────────────────────── */
.module { margin: 1.25rem 0; }
.module-name {
  background: #f0f0f0; border-radius: 4px;
  padding: .35rem .75rem; font-weight: 700;
  font-size: .95rem; letter-spacing: .02em;
}
.module ul, .module ol { padding-left: 1.5rem; margin: .3rem 0; }
.module li { margin-bottom: .2rem; }
.module-key { font-weight: 600; color: #444; font-size: .85rem; text-transform: uppercase;
  letter-spacing: .04em; margin: .6rem 0 .2rem; }

/* ── Recommendations ────────────────────────────────────── */
ol.recs { padding-left: 1.5rem; }
ol.recs li { margin-bottom: .5rem; }

/* ── Sources ────────────────────────────────────────────── */
ol.sources { font-size: .83rem; color: #444; padding-left: 1.5rem; }
ol.sources li { margin-bottom: .3rem; word-break: break-word; }

/* ── Audit summary ──────────────────────────────────────── */
.audit-box {
  background: #f9f9f9; border: 1px solid #e0e0e0;
  border-radius: 6px; padding: 1rem 1.25rem;
  font-size: .88rem; margin: 1.5rem 0;
}
.audit-box h2 { border: none; margin: 0 0 .7rem; font-size: 1rem; color: #333; padding: 0; }
table.audit-table { border-collapse: collapse; width: 100%; }
table.audit-table td { padding: .2rem .5rem; vertical-align: middle; }
table.audit-table td:first-child { font-weight: 600; color: #555; white-space: nowrap; width: 1%; padding-right: 1.2rem; }
.audit-pass { color: #1e7c3a; font-weight: 700; }
.audit-fail { color: #b52a2a; font-weight: 700; }
.audit-warn { color: #c47d00; font-weight: 700; }
.audit-failures { margin: .5rem 0 0; padding-left: 1.4rem; font-size: .85rem; color: #555; }
.audit-failures li { margin-bottom: .2rem; }
p.audit-section-label { margin: .8rem 0 .2rem; font-size: .82rem; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: .04em; }

/* ── Disclaimer note ────────────────────────────────────── */
.disclaimer {
  background: #fff8e6; border: 1px solid #f0c040;
  border-radius: 4px; padding: .6rem 1rem;
  font-size: .9rem; margin: .75rem 0 1.25rem;
}

@media (max-width: 600px) { body { padding: 1rem; } }
@media print { body { max-width: 100%; padding: 0; } }
"""


# ── Helpers ────────────────────────────────────────────────────────────────

def _e(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def _cite(text: str) -> str:
    """HTML-escape then convert [N] markers to clickable anchors."""
    escaped = _e(text)
    return _CITE_RE.sub(
        lambda m: f'<a href="#src-{m.group(1)}" class="cite">[{m.group(1)}]</a>',
        escaped,
    )


def _linkify_source(text: str) -> str:
    """HTML-escape a source entry and auto-link any URL."""
    escaped = _e(text)
    return _URL_RE.sub(r'<a href="\1">\1</a>', escaped)


def _flag_class(flag: str) -> str:
    lower = flag.lower()
    if lower.startswith("red:"):    return "flag-red"
    if lower.startswith("yellow:"): return "flag-yellow"
    if lower.startswith("green:"):  return "flag-green"
    return ""


# ── Helpers ────────────────────────────────────────────────────────────────

def _format_date(iso: str) -> str:
    """Format an ISO timestamp as 'DD Month YYYY'."""
    if not iso:
        return datetime.now(timezone.utc).strftime("%-d %B %Y")
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%-d %B %Y")
    except ValueError:
        return iso


def _section_toc(analysis: FinalAnalysis, report_style: str) -> str:
    """Build a linked table of contents based on what sections will render."""
    entries = []

    if report_style != "customer":
        entries.append(("config", "Analysis Configuration"))

    if report_style == "detailed":
        entries.append(("synthesis", "TL;DR — Final Analysis"))
    else:
        if analysis.priority_flags or analysis.synthesis:
            entries.append(("synthesis", "Synthesis"))

    if analysis.conflicts:
        entries.append(("conflicts", "Conflicts Identified"))

    if analysis.recommendations:
        entries.append(("recommendations", "Recommendations"))

    if analysis.conflict_resolutions and report_style == "detailed":
        entries.append(("deep-research", "Deep Research"))

    if report_style == "detailed":
        round1 = [o for o in analysis.module_outputs if o.round == 1]
        round2 = [o for o in analysis.module_outputs if o.round == 2]
        if round1:
            entries.append(("round-1", "Round 1 — Independent Analysis"))
        if round2:
            entries.append(("round-2", "Round 2 — Cross-Module Revision"))

    if analysis.audit:
        entries.append(("audit", "Source &amp; Integrity Audit"))

    if analysis.sources:
        entries.append(("sources", "Sources &amp; References"))

    if not entries:
        return ""

    items = "".join(f"<li><a href='#{sid}'>{label}</a></li>" for sid, label in entries)
    return f"<nav class='toc'><strong>Contents</strong><ol>{items}</ol></nav>"


# ── Section builders ───────────────────────────────────────────────────────

def _section_config(analysis: FinalAnalysis) -> str:
    active = list(dict.fromkeys(o.module_name for o in analysis.module_outputs))

    # Module weights table — always shown, highlights non-default weights
    weight_rows = []
    for name in active:
        w = analysis.weights.get(name, 1.0)
        weight_cell = f"<strong>{w}x</strong>" if w != 1.0 else "1.0x"
        weight_rows.append(f"<tr><td>{_e(name)}</td><td>{weight_cell}</td></tr>")
    modules_table = (
        f"<table class='weights'>"
        f"<tr><th>Module</th><th>Weight</th></tr>"
        f"{''.join(weight_rows)}"
        f"</table>"
    )

    deactivated = [
        name for name, w in analysis.weights.items()
        if w == 0 and name not in active
    ]

    search_status = "enabled" if analysis.search_enabled else "disabled"
    if analysis.search_enabled and analysis.sources:
        search_status += f" &mdash; {len(analysis.sources)} sources fetched"

    rows = [("Web search", search_status)]
    if deactivated:
        rows.append(("Deactivated", ", ".join(_e(d) for d in deactivated)))

    meta = analysis.selection_metadata
    if meta and meta.ad_hoc_modules:
        rows.append(("Ad-hoc modules", ", ".join(_e(m.name) for m in meta.ad_hoc_modules)))
    if analysis.deep_research_enabled:
        rows.append(("Deep research", "enabled"))

    info_trs = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)

    return (
        f"<div class='config-box'>"
        f"<div class='config-cols'>"
        f"<div><div class='config-label'>Modules &amp; Weights</div>{modules_table}</div>"
        f"<div><table>{info_trs}</table></div>"
        f"</div>"
        f"</div>"
    )


def _section_selection_metadata(analysis: FinalAnalysis) -> str:
    meta = analysis.selection_metadata
    if not meta or not meta.auto_selected:
        return ""
    parts = [
        f"<h2>Adaptive Module Selection</h2>",
        f"<p><strong>Selected:</strong> {_e(', '.join(meta.selected_modules))}</p>",
        f"<p><strong>Reasoning:</strong> {_e(meta.selection_reasoning)}</p>",
    ]
    if meta.gap_check_reasoning:
        parts.append(f"<p><strong>Gap check:</strong> {_e(meta.gap_check_reasoning)}</p>")
    return "".join(parts)


def _section_flags(flags: List[str]) -> str:
    if not flags:
        return ""
    items = []
    for flag in flags:
        cls = _flag_class(flag)
        items.append(f"<li class='{cls}'>{_cite(flag)}</li>")
    return f"<h3>Priority Flags</h3><ul class='flags'>{''.join(items)}</ul>"


def _section_synthesis(text: str) -> str:
    if not text:
        return ""
    return f"<h3>Synthesis</h3><p>{_cite(text)}</p>"


def _section_conflicts(conflicts: List[Conflict], anchor: bool = False) -> str:
    if not conflicts:
        return ""
    id_attr = " id='conflicts'" if anchor else ""
    items = []
    for c in conflicts:
        cls = c.severity.lower()
        modules = " vs ".join(_e(m) for m in c.modules)
        arbitration_html = ""
        if c.arbitration:
            arbitration_html = (
                f"<div class='conflict-arbitration'>"
                f"<strong>Authority: {_e(c.arbitration.authority)}</strong>"
                f" — {_e(c.arbitration.reasoning)}"
                f"</div>"
            )
        items.append(
            f"<div class='conflict {cls}'>"
            f"<div class='conflict-label'>[{_e(c.severity.upper())}] {modules} — {_e(c.topic)}</div>"
            f"<div>{_cite(c.description)}</div>"
            f"{arbitration_html}"
            f"</div>"
        )
    heading = f"<h3{id_attr}>Conflicts Identified</h3>"
    return f"{heading}{''.join(items)}"


def _section_recommendations(recs: List[str]) -> str:
    if not recs:
        return ""
    items = "".join(f"<li>{_cite(r)}</li>" for r in recs)
    return f"<h3>Recommendations</h3><ol class='recs'>{items}</ol>"


def _section_deep_research(resolutions: List[ConflictResolution]) -> str:
    if not resolutions:
        return ""
    items = []
    for res in resolutions:
        if res.modules:
            label = f"[{res.severity.upper()}] {' vs '.join(_e(m) for m in res.modules)} — {_e(res.topic)}"
        else:
            label = f"[RED FLAG] {_e(res.topic)}"
        items.append(
            f"<div class='resolution'>"
            f"<div class='resolution-label'>{label}</div>"
            f"<div class='resolution-verdict'><strong>Verdict:</strong> {_cite(res.verdict)}</div>"
            f"<div class='resolution-rec'><strong>Updated recommendation:</strong> {_cite(res.updated_recommendation)}</div>"
            f"</div>"
        )
    return f"<h2>Deep Research — Conflict &amp; Flag Resolutions</h2>{''.join(items)}"


def _section_module_detail(output: ModuleOutput) -> str:
    parts = [f"<div class='module'><div class='module-name'>{_e(output.module_name.upper())}</div>"]
    for key, value in output.analysis.items():
        parts.append(f"<div class='module-key'>{_e(key)}</div>")
        if isinstance(value, list):
            items = "".join(f"<li>{_cite(str(v))}</li>" for v in value)
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{_cite(str(value))}</p>")
    if output.flags:
        flag_items = []
        for flag in output.flags:
            cls = _flag_class(flag)
            flag_items.append(f"<li class='{cls}'>{_cite(flag)}</li>")
        parts.append(f"<div class='module-key'>Flags</div><ul class='flags'>{''.join(flag_items)}</ul>")
    parts.append("</div>")
    return "".join(parts)


def _section_audit(analysis: FinalAnalysis) -> str:
    audit = analysis.audit
    if not audit:
        return ""

    def _badge(passed: bool) -> str:
        return "<span class='audit-pass'>&#10003; PASS</span>" if passed \
               else "<span class='audit-fail'>&#10007; FAIL</span>"

    rows = [
        ("Prompt constraints", _badge(audit.layer1_passed)),
        ("Citation integrity", _badge(audit.layer2_passed)),
    ]

    if audit.layer3_total:
        pct = int(100 * audit.layer3_ok / audit.layer3_total)
        reachable = f"{audit.layer3_ok}/{audit.layer3_total} reachable ({pct}%)"
        if audit.layer3_failures:
            reachable += " <span class='audit-warn'>&#9888; issues below</span>"
        rows.append(("URL reachability", reachable))

    if audit.layer4_ran:
        results = audit.layer4_results
        by_verdict: dict = {}
        for r in results:
            by_verdict.setdefault(r.verdict, []).append(r)
        total = len(results)
        supported = len(by_verdict.get("SUPPORTED", []))
        partial = len(by_verdict.get("PARTIAL", []))
        unsupported = len(by_verdict.get("UNSUPPORTED", []))
        failed = len(by_verdict.get("FETCH_FAILED", [])) + len(by_verdict.get("UNKNOWN", []))
        summary = f"{supported}/{total} supported"
        if partial:
            summary += f", {partial} partial"
        if unsupported:
            summary += f", {unsupported} unsupported"
        if failed:
            summary += f", {failed} fetch failed"
        if unsupported or failed:
            summary += " <span class='audit-warn'>&#9888; issues below</span>"
        rows.append(("Grounding check", summary if total else "No citations sampled"))

    if audit.layer5_ran:
        results5 = audit.layer5_results
        total5 = len(results5)
        ok5 = sum(1 for r in results5 if r.ok)
        badge = _badge(ok5 == total5) if total5 else "<span class='audit-warn'>No pairs found</span>"
        rows.append(("R1→R2 consistency", f"{ok5}/{total5} modules consistent &nbsp;{badge}" if total5 else badge))

    trs = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    table = f"<table class='audit-table'>{trs}</table>"

    violations_html = ""
    all_violations = audit.layer1_violations + audit.layer2_violations
    if all_violations:
        items = "".join(f"<li>{_e(v)}</li>" for v in all_violations)
        violations_html = f"<ul class='audit-failures'>{items}</ul>"

    failures_html = ""
    if audit.layer3_failures:
        items = []
        for f in audit.layer3_failures:
            status = f.status or "ERR"
            note = f.error or ""
            items.append(f"<li><code>[{status}]</code> <a href='{_e(f.url)}'>{_e(f.url)}</a> {_e(note)}</li>")
        failures_html = f"<ul class='audit-failures'>{''.join(items)}</ul>"

    layer4_html = ""
    if audit.layer4_ran and audit.layer4_results:
        bad = [r for r in audit.layer4_results if r.verdict != "SUPPORTED"]
        if bad:
            items = []
            icons = {"PARTIAL": "~", "UNSUPPORTED": "✗", "FETCH_FAILED": "?", "UNKNOWN": "?"}
            for r in bad:
                icon = icons.get(r.verdict, "?")
                items.append(
                    f"<li><code>{_e(r.citation)}</code> "
                    f"<span class='audit-warn'>{icon} {_e(r.verdict)}</span> "
                    f"— {_e(r.sentence[:140])}{'…' if len(r.sentence) > 140 else ''} "
                    f"<a href='{_e(r.url)}'>[source]</a></li>"
                )
            layer4_html = f"<p class='audit-section-label'>Grounding issues:</p><ul class='audit-failures'>{''.join(items)}</ul>"

    layer5_html = ""
    if audit.layer5_ran and audit.layer5_results:
        bad5 = [r for r in audit.layer5_results if not r.ok]
        if bad5:
            items = []
            for r in bad5:
                issue_list = "".join(f"<li>{_e(i)}</li>" for i in r.issues)
                items.append(f"<li><strong>{_e(r.module)}</strong><ul>{issue_list}</ul></li>")
            layer5_html = f"<p class='audit-section-label'>Consistency issues:</p><ul class='audit-failures'>{''.join(items)}</ul>"

    return (
        f"<div class='audit-box'>"
        f"<h2>Source &amp; Integrity Audit</h2>"
        f"{table}{violations_html}{failures_html}{layer4_html}{layer5_html}"
        f"</div>"
    )


def _section_sources(sources: List[str]) -> str:
    if not sources:
        return ""
    items = "".join(
        f"<li id='src-{i}'>{_linkify_source(src)}</li>"
        for i, src in enumerate(sources, 1)
    )
    return f"<h2>Sources &amp; References</h2><ol class='sources'>{items}</ol>"


# ── Public entry point ─────────────────────────────────────────────────────

def format_html_report(analysis: FinalAnalysis, report_style: str = "default") -> str:
    title = _e(f"Analysis Brief — {analysis.problem}")

    # ── Header ──────────────────────────────────────────────
    date_str = _format_date(analysis.generated_at)
    source_count = f" &nbsp;·&nbsp; {len(analysis.sources)} sources" if analysis.sources else ""
    body_parts = [
        f"<h1>Analysis Brief</h1>",
        f"<p class='subtitle'>Provided by your AI-powered analyst panel &mdash; multi-perspective intelligence, synthesized.</p>",
        f"<p class='meta'>Generated: {date_str}{source_count}</p>",
        f"<p><strong>Analysis Subject:</strong> {_e(analysis.problem)}</p>",
    ]

    # ── Table of contents ────────────────────────────────────
    body_parts.append(_section_toc(analysis, report_style))

    if report_style != "customer":
        body_parts.append(f"<div id='config'>{_section_config(analysis)}</div>")
        body_parts.append(_section_selection_metadata(analysis))

    if analysis.deactivated_disclaimer:
        body_parts.append(f"<div class='disclaimer'>{_e(analysis.deactivated_disclaimer)}</div>")

    # ── TL;DR / Synthesis block ──────────────────────────────
    body_parts.append("<section>")
    if report_style == "detailed":
        body_parts.append("<h2 id='synthesis'>TL;DR &mdash; Final Analysis</h2>")
    else:
        body_parts.append("<span id='synthesis'></span>")
    body_parts.append(_section_flags(analysis.priority_flags))
    body_parts.append(_section_synthesis(analysis.synthesis))
    body_parts.append(_section_conflicts(analysis.conflicts, anchor=True))
    if analysis.recommendations:
        body_parts.append(f"<div id='recommendations'>{_section_recommendations(analysis.recommendations)}</div>")
    body_parts.append("</section>")

    # ── Deep research (detailed only) ────────────────────────
    if report_style == "detailed":
        dr = _section_deep_research(analysis.conflict_resolutions)
        if dr:
            body_parts.append(f"<section id='deep-research'>{dr}</section>")

    # ── Module evidence (detailed only) ──────────────────────
    if report_style == "detailed":
        round1 = [o for o in analysis.module_outputs if o.round == 1]
        round2 = [o for o in analysis.module_outputs if o.round == 2]
        if round1:
            body_parts.append("<section id='round-1'><h2>Round 1 &mdash; Independent Analysis</h2>")
            for o in round1:
                body_parts.append(_section_module_detail(o))
            body_parts.append("</section>")
        if round2:
            body_parts.append("<section id='round-2'><h2>Round 2 &mdash; Cross-Module Revision</h2>")
            for o in round2:
                body_parts.append(_section_module_detail(o))
            body_parts.append("</section>")

    body_parts.append(f"<div id='audit'>{_section_audit(analysis)}</div>")
    body_parts.append(f"<div id='sources'>{_section_sources(analysis.sources)}</div>")

    body = "\n".join(body_parts)
    return (
        f"<!DOCTYPE html>\n"
        f"<html lang='en'>\n"
        f"<head>\n"
        f"  <meta charset='utf-8'>\n"
        f"  <meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        f"  <title>{title}</title>\n"
        f"  <style>{_CSS}</style>\n"
        f"</head>\n"
        f"<body>\n{body}\n</body>\n"
        f"</html>\n"
    )
