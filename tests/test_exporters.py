import json
import os

import pytest

from src.models.schemas import Conflict, FinalAnalysis, ModuleOutput
from src.utils.exporters import export_all, export_html, export_json, export_markdown, export_to_file, strip_ansi, _slugify


@pytest.fixture
def sample_analysis():
    return FinalAnalysis(
        problem="Should we build a food delivery app?",
        module_outputs=[
            ModuleOutput(
                module_name="market",
                round=1,
                analysis={"summary": "High demand in urban areas"},
                flags=["green: strong market"],
                sources=["IBISWorld 2024"],
            ),
            ModuleOutput(
                module_name="cost",
                round=2,
                analysis={"summary": "High burn rate expected"},
                flags=["yellow: capital intensive"],
                sources=["Crunchbase 2024"],
                revised=True,
            ),
        ],
        conflicts=[
            Conflict(
                modules=["market", "cost"],
                topic="burn rate",
                description="Market sees demand but cost flags high burn",
                severity="high",
            )
        ],
        synthesis="Viable but requires careful funding.",
        recommendations=["Start in one city", "Secure Series A"],
        priority_flags=["yellow: high investment required"],
        sources=["Deloitte 2024", "McKinsey Survey"],
    )


class TestStripAnsi:
    def test_removes_color_codes(self):
        assert strip_ansi("\033[91mred text\033[0m") == "red text"

    def test_removes_bold(self):
        assert strip_ansi("\033[1mbold\033[0m") == "bold"

    def test_no_ansi_unchanged(self):
        assert strip_ansi("plain text") == "plain text"

    def test_multiple_codes(self):
        text = "\033[1m\033[96m[MARKET]\033[0m some text \033[93mflag\033[0m"
        result = strip_ansi(text)
        assert "\033" not in result
        assert "[MARKET]" in result
        assert "flag" in result


class TestExportMarkdown:
    def test_default_style(self, sample_analysis):
        md = export_markdown(sample_analysis, "default")
        assert "\033" not in md
        assert "FINAL ANALYSIS" in md
        assert sample_analysis.problem in md

    def test_detailed_style(self, sample_analysis):
        md = export_markdown(sample_analysis, "detailed")
        assert "\033" not in md
        assert "DETAILED ANALYSIS REPORT" in md

    def test_customer_style(self, sample_analysis):
        md = export_markdown(sample_analysis, "customer")
        assert "\033" not in md
        assert "ANALYSIS REPORT" in md
        assert "Round 1" not in md

    def test_contains_recommendations(self, sample_analysis):
        md = export_markdown(sample_analysis, "default")
        assert "Start in one city" in md
        assert "Secure Series A" in md

    def test_contains_sources(self, sample_analysis):
        md = export_markdown(sample_analysis, "default")
        assert "Deloitte 2024" in md


class TestExportJson:
    def test_valid_json(self, sample_analysis):
        raw = export_json(sample_analysis)
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_contains_fields(self, sample_analysis):
        data = json.loads(export_json(sample_analysis))
        assert data["problem"] == sample_analysis.problem
        assert data["synthesis"] == sample_analysis.synthesis
        assert data["recommendations"] == sample_analysis.recommendations
        assert data["sources"] == sample_analysis.sources
        assert len(data["module_outputs"]) == 2

    def test_module_outputs_structure(self, sample_analysis):
        data = json.loads(export_json(sample_analysis))
        mo = data["module_outputs"][0]
        assert "module_name" in mo
        assert "round" in mo
        assert "analysis" in mo


class TestExportHtml:
    def test_contains_html_tags(self, sample_analysis):
        html = export_html(sample_analysis)
        assert "<html>" in html
        assert "</html>" in html
        assert "<pre>" in html

    def test_no_ansi(self, sample_analysis):
        html = export_html(sample_analysis)
        assert "\033" not in html

    def test_contains_content(self, sample_analysis):
        html = export_html(sample_analysis)
        assert sample_analysis.problem in html

    def test_customer_style(self, sample_analysis):
        html = export_html(sample_analysis, "customer")
        assert "ANALYSIS REPORT" in html

    def test_auto_links_urls(self):
        analysis = FinalAnalysis(
            problem="test",
            sources=["https://example.com/report", "Some text report"],
        )
        html = export_html(analysis)
        assert '<a href="https://example.com/report">https://example.com/report</a>' in html
        assert "Some text report" in html


class TestExportToFile:
    def test_write_markdown(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report.md")
        export_to_file(sample_analysis, path)
        content = open(path).read()
        assert "FINAL ANALYSIS" in content
        assert "\033" not in content

    def test_write_json(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report.json")
        export_to_file(sample_analysis, path)
        data = json.loads(open(path).read())
        assert data["problem"] == sample_analysis.problem

    def test_write_html(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report.html")
        export_to_file(sample_analysis, path, "customer")
        content = open(path).read()
        assert "<html>" in content

    def test_unsupported_extension(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report.pdf")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            export_to_file(sample_analysis, path)

    def test_no_extension(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report")
        with pytest.raises(ValueError, match="Unsupported file extension"):
            export_to_file(sample_analysis, path)

    def test_report_style_passed_through(self, sample_analysis, tmp_path):
        path = str(tmp_path / "report.md")
        export_to_file(sample_analysis, path, "detailed")
        content = open(path).read()
        assert "DETAILED ANALYSIS REPORT" in content


class TestSlugify:
    def test_basic(self):
        assert _slugify("Should we build a food delivery app?") == "should-we-build-a-food-delivery-app"

    def test_special_chars(self):
        assert _slugify("AI/ML & Data: 2024!") == "ai-ml-data-2024"

    def test_truncation(self):
        long = "a " * 50
        slug = _slugify(long)
        assert len(slug) <= 60

    def test_no_trailing_dash(self):
        slug = _slugify("a " * 50)
        assert not slug.endswith("-")

    def test_empty_string(self):
        assert _slugify("???") == "analysis"


class TestExportAll:
    def test_creates_directory_structure(self, sample_analysis, tmp_path):
        out_dir = export_all(sample_analysis, base_dir=str(tmp_path))
        assert os.path.isdir(out_dir)
        # Should be <base>/<slug>/<timestamp>
        parts = os.path.relpath(out_dir, tmp_path).split(os.sep)
        assert len(parts) == 2

    def test_writes_all_three_files(self, sample_analysis, tmp_path):
        out_dir = export_all(sample_analysis, base_dir=str(tmp_path))
        assert os.path.isfile(os.path.join(out_dir, "report.md"))
        assert os.path.isfile(os.path.join(out_dir, "report.json"))
        assert os.path.isfile(os.path.join(out_dir, "report.html"))

    def test_file_contents(self, sample_analysis, tmp_path):
        out_dir = export_all(sample_analysis, base_dir=str(tmp_path))
        md = open(os.path.join(out_dir, "report.md")).read()
        assert "FINAL ANALYSIS" in md
        data = json.loads(open(os.path.join(out_dir, "report.json")).read())
        assert data["problem"] == sample_analysis.problem
        html = open(os.path.join(out_dir, "report.html")).read()
        assert "<html>" in html

    def test_report_style_applied(self, sample_analysis, tmp_path):
        out_dir = export_all(sample_analysis, report_style="customer", base_dir=str(tmp_path))
        md = open(os.path.join(out_dir, "report.md")).read()
        assert "ANALYSIS REPORT" in md

    def test_slug_in_path(self, sample_analysis, tmp_path):
        out_dir = export_all(sample_analysis, base_dir=str(tmp_path))
        assert "should-we-build-a-food-delivery-app" in out_dir
