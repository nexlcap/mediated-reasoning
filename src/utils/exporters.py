import json
import os
import re
from datetime import datetime

from src.models.schemas import FinalAnalysis
from src.utils.formatters import (
    format_customer_report,
    format_detailed_report,
    format_final_analysis,
)
from src.utils.html_formatter import format_html_report

ANSI_RE = re.compile(r"\033\[[0-9;]*m")
URL_RE = re.compile(r"(https?://[^\s<>&]+)")
# Matches [LABEL] where label is not a plain integer (i.e. not a source ref like [1])
MD_BRACKET_RE = re.compile(r"\[([^0-9\]][^\]]*)\](?!\()")

FORMATTERS = {
    "default": format_final_analysis,
    "detailed": format_detailed_report,
    "customer": format_customer_report,
}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def export_markdown(analysis: FinalAnalysis, report_style: str = "default") -> str:
    formatter = FORMATTERS[report_style]
    text = strip_ansi(formatter(analysis))
    # Escape [LABEL] bracket patterns so markdown editors don't render them as link syntax
    text = MD_BRACKET_RE.sub(r"\[\1\]", text)
    return text


def export_json(analysis: FinalAnalysis) -> str:
    return json.dumps(analysis.model_dump(), indent=2)


def export_html(analysis: FinalAnalysis, report_style: str = "default") -> str:
    return format_html_report(analysis, report_style)


EXPORTERS = {
    ".md": lambda a, s: export_markdown(a, s),
    ".json": lambda a, _s: export_json(a),
    ".html": lambda a, s: export_html(a, s),
}


def export_to_file(analysis: FinalAnalysis, path: str, report_style: str = "default") -> None:
    ext = _get_extension(path)
    exporter = EXPORTERS.get(ext)
    if exporter is None:
        raise ValueError(f"Unsupported file extension '{ext}'. Supported: {', '.join(EXPORTERS)}")
    content = exporter(analysis, report_style)
    with open(path, "w") as f:
        f.write(content)


def _get_extension(path: str) -> str:
    dot = path.rfind(".")
    if dot == -1:
        return ""
    return path[dot:]


def _slugify(text: str, max_length: int = 60) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "analysis"


def export_all(
    analysis: FinalAnalysis,
    report_style: str = "default",
    base_dir: str = "output",
) -> str:
    slug = _slugify(analysis.problem)
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    out_dir = os.path.join(base_dir, slug, timestamp)
    os.makedirs(out_dir, exist_ok=True)

    for ext, exporter in EXPORTERS.items():
        content = exporter(analysis, report_style)
        with open(os.path.join(out_dir, f"report{ext}"), "w") as f:
            f.write(content)

    return out_dir
