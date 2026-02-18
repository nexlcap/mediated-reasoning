"""
Semantic HTML report generator for FinalAnalysis objects.

Generates clean, readable HTML directly from the data model — no terminal
escape codes, no <pre> blocks, no long unwrapped lines.
"""
import html
import re
from typing import List

from src.models.schemas import Conflict, ConflictResolution, FinalAnalysis, ModuleOutput

_CITE_RE = re.compile(r"\[(\d+)\]")
_URL_RE = re.compile(r"(https?://[^\s<>&\"]+)")

_CSS = """
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  max-width: 880px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  line-height: 1.7;
  color: #1a1a1a;
  background: #fff;
}
h1 { font-size: 1.55rem; border-bottom: 2px solid #ddd; padding-bottom: .4rem; margin-bottom: 1.5rem; }
h2 { font-size: 1.15rem; margin: 2.2rem 0 .7rem; color: #111; border-bottom: 1px solid #eee; padding-bottom: .2rem; }
h3 { font-size: 1rem; margin: 1.4rem 0 .4rem; color: #333; }
p  { margin: .5rem 0; }
a  { color: #1a5ba6; word-break: break-all; }
a.cite { text-decoration: none; color: #555; font-size: .85em; }
a.cite:hover { text-decoration: underline; }

/* ── Config box ─────────────────────────────────────────── */
.config-box {
  background: #f8f8f8;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 1rem 1.25rem;
  font-size: .9rem;
  margin-bottom: 1.5rem;
}
.config-box table { border-collapse: collapse; width: 100%; }
.config-box td { padding: .2rem .4rem; vertical-align: top; }
.config-box td:first-child {
  font-weight: 600; color: #555;
  white-space: nowrap; width: 1%;
  padding-right: 1.2rem;
}
table.raci { border-collapse: collapse; width: 100%; font-size: .85rem; margin-top: .6rem; }
table.raci th, table.raci td { border: 1px solid #ddd; padding: .35rem .6rem; text-align: left; }
table.raci th { background: #f0f0f0; font-weight: 600; }

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


# ── Section builders ───────────────────────────────────────────────────────

def _section_config(analysis: FinalAnalysis) -> str:
    active = list(dict.fromkeys(o.module_name for o in analysis.module_outputs))
    module_parts = []
    for name in active:
        w = analysis.weights.get(name, 1)
        module_parts.append(f"{_e(name)} ({w}x)" if w != 1 else _e(name))

    deactivated = [
        name for name, w in analysis.weights.items()
        if w == 0 and name not in active
    ]

    search_status = "enabled" if analysis.search_enabled else "disabled"
    if analysis.search_enabled and analysis.sources:
        search_status += f" ({len(analysis.sources)} sources fetched)"

    rows = [
        ("Modules", ", ".join(module_parts)),
        ("Web search", search_status),
    ]
    if deactivated:
        rows.append(("Deactivated", ", ".join(_e(d) for d in deactivated)))

    meta = analysis.selection_metadata
    if meta and meta.ad_hoc_modules:
        rows.append(("Ad-hoc modules", ", ".join(_e(m.name) for m in meta.ad_hoc_modules)))
    if analysis.deep_research_enabled:
        rows.append(("Deep research", "enabled"))

    trs = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows
    )
    raci_html = ""
    if analysis.raci_matrix:
        header = "<tr><th>Topic</th><th>Responsible</th><th>Accountable</th><th>Consulted</th><th>Informed</th></tr>"
        raci_rows = []
        for topic, roles in analysis.raci_matrix.items():
            c = ", ".join(roles["C"]) if isinstance(roles.get("C"), list) else (roles.get("C") or "")
            i = ", ".join(roles["I"]) if isinstance(roles.get("I"), list) else (roles.get("I") or "")
            raci_rows.append(
                f"<tr><td>{_e(topic)}</td><td>{_e(roles.get('R',''))}</td>"
                f"<td>{_e(roles.get('A',''))}</td><td>{_e(c)}</td><td>{_e(i)}</td></tr>"
            )
        raci_html = f"<table class='raci'>{header}{''.join(raci_rows)}</table>"

    return (
        f"<div class='config-box'>"
        f"<table>{trs}</table>"
        f"{raci_html}"
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


def _section_conflicts(conflicts: List[Conflict]) -> str:
    if not conflicts:
        return ""
    items = []
    for c in conflicts:
        cls = c.severity.lower()
        modules = " vs ".join(_e(m) for m in c.modules)
        items.append(
            f"<div class='conflict {cls}'>"
            f"<div class='conflict-label'>[{_e(c.severity.upper())}] {modules} — {_e(c.topic)}</div>"
            f"<div>{_cite(c.description)}</div>"
            f"</div>"
        )
    return f"<h3>Conflicts Identified</h3>{''.join(items)}"


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
    title = _e(f"Analysis Report — {analysis.problem}")
    body_parts = [f"<h1>Analysis Report</h1><p><strong>Problem:</strong> {_e(analysis.problem)}</p>"]

    if report_style != "customer":
        body_parts.append(_section_config(analysis))
        body_parts.append(_section_selection_metadata(analysis))

    if analysis.deactivated_disclaimer:
        body_parts.append(f"<div class='disclaimer'>{_e(analysis.deactivated_disclaimer)}</div>")

    # TL;DR block
    body_parts.append("<section>")
    if report_style == "detailed":
        body_parts.append("<h2>TL;DR — Final Analysis</h2>")
    body_parts.append(_section_flags(analysis.priority_flags))
    body_parts.append(_section_synthesis(analysis.synthesis))
    body_parts.append(_section_conflicts(analysis.conflicts))
    body_parts.append(_section_recommendations(analysis.recommendations))
    body_parts.append("</section>")

    # Deep research (detailed only)
    if report_style == "detailed":
        dr = _section_deep_research(analysis.conflict_resolutions)
        if dr:
            body_parts.append(f"<section>{dr}</section>")

    # Module evidence (detailed only)
    if report_style == "detailed":
        round1 = [o for o in analysis.module_outputs if o.round == 1]
        round2 = [o for o in analysis.module_outputs if o.round == 2]
        if round1:
            body_parts.append("<section><h2>Round 1 — Independent Analysis</h2>")
            for o in round1:
                body_parts.append(_section_module_detail(o))
            body_parts.append("</section>")
        if round2:
            body_parts.append("<section><h2>Round 2 — Cross-Module Revision</h2>")
            for o in round2:
                body_parts.append(_section_module_detail(o))
            body_parts.append("</section>")

    body_parts.append(_section_sources(analysis.sources))

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
