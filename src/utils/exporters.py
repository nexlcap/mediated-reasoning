import json
import re

from src.models.schemas import FinalAnalysis
from src.utils.formatters import (
    format_customer_report,
    format_detailed_report,
    format_final_analysis,
)

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

FORMATTERS = {
    "default": format_final_analysis,
    "detailed": format_detailed_report,
    "customer": format_customer_report,
}


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def export_markdown(analysis: FinalAnalysis, report_style: str = "default") -> str:
    formatter = FORMATTERS[report_style]
    return strip_ansi(formatter(analysis))


def export_json(analysis: FinalAnalysis) -> str:
    return json.dumps(analysis.model_dump(), indent=2)


def export_html(analysis: FinalAnalysis, report_style: str = "default") -> str:
    formatter = FORMATTERS[report_style]
    content = strip_ansi(formatter(analysis))
    # Escape HTML entities in the content
    content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head><meta charset=\"utf-8\"><title>Analysis Report</title></head>\n"
        "<body>\n"
        f"<pre>{content}</pre>\n"
        "</body>\n"
        "</html>\n"
    )


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
