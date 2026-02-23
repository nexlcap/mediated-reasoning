"""Tests for src/project_memory.py"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.project_memory import ProjectMemory, BRIEF_TEMPLATE


@pytest.fixture()
def tmp_project(tmp_path):
    """Return a ProjectMemory instance pointing at a fresh temp dir."""
    return ProjectMemory(str(tmp_path / "my-project"))


class TestLoad:
    def test_creates_dirs_on_new_project(self, tmp_project):
        tmp_project.load()
        assert tmp_project.project_dir.is_dir()
        assert tmp_project.sessions_dir.is_dir()

    def test_creates_template_brief_on_new_project(self, tmp_project):
        content = tmp_project.load()
        assert tmp_project.brief_path.exists()
        assert "## Stage" in content
        assert "## Open questions" in content

    def test_reads_existing_brief(self, tmp_project):
        tmp_project.project_dir.mkdir(parents=True)
        tmp_project.sessions_dir.mkdir(parents=True)
        custom = "## Stage\nPre-revenue\n"
        tmp_project.brief_path.write_text(custom)
        assert tmp_project.load() == custom

    def test_does_not_overwrite_existing_brief(self, tmp_project):
        tmp_project.project_dir.mkdir(parents=True)
        tmp_project.sessions_dir.mkdir(parents=True)
        original = "## Stage\nBootstrapped\n"
        tmp_project.brief_path.write_text(original)
        tmp_project.load()
        assert tmp_project.brief_path.read_text() == original

    def test_idempotent(self, tmp_project):
        first = tmp_project.load()
        second = tmp_project.load()
        assert first == second


class TestBriefAsContext:
    def test_returns_formatted_string(self, tmp_project):
        tmp_project.load()
        ctx = tmp_project.brief_as_context()
        assert ctx.startswith("Project brief:\n")
        assert "## Stage" in ctx

    def test_strips_trailing_whitespace(self, tmp_project):
        tmp_project.project_dir.mkdir(parents=True)
        tmp_project.sessions_dir.mkdir(parents=True)
        tmp_project.brief_path.write_text("## Stage\nEarly\n\n\n")
        ctx = tmp_project.brief_as_context()
        assert not ctx.endswith("\n\n")


class TestSaveSession:
    def _make_result(self, **kwargs):
        r = MagicMock()
        r.problem = kwargs.get("problem", "Test problem")
        r.synthesis = kwargs.get("synthesis", "Test synthesis")
        r.recommendations = kwargs.get("recommendations", ["Do A", "Do B"])
        return r

    def test_creates_session_file(self, tmp_project):
        tmp_project.load()
        path = tmp_project.save_session(self._make_result(), [])
        assert Path(path).exists()

    def test_session_file_is_in_sessions_dir(self, tmp_project):
        tmp_project.load()
        path = tmp_project.save_session(self._make_result(), [])
        assert Path(path).parent == tmp_project.sessions_dir

    def test_session_file_named_by_date(self, tmp_project):
        tmp_project.load()
        path = tmp_project.save_session(self._make_result(), [])
        filename = Path(path).name
        # Should match YYYY-MM-DD.md
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}\.md", filename)

    def test_appends_on_second_call(self, tmp_project):
        tmp_project.load()
        r = self._make_result()
        path = tmp_project.save_session(r, [])
        tmp_project.save_session(r, [])
        content = Path(path).read_text()
        # Two session headers
        assert content.count("## Session") == 2

    def test_includes_problem(self, tmp_project):
        tmp_project.load()
        r = self._make_result(problem="Should I build a SaaS?")
        path = tmp_project.save_session(r, [])
        assert "Should I build a SaaS?" in Path(path).read_text()

    def test_includes_recommendations(self, tmp_project):
        tmp_project.load()
        r = self._make_result(recommendations=["Launch fast", "Stay lean"])
        path = tmp_project.save_session(r, [])
        content = Path(path).read_text()
        assert "Launch fast" in content
        assert "Stay lean" in content

    def test_includes_qa_pairs(self, tmp_project):
        tmp_project.load()
        r = self._make_result()
        qa = [("What about costs?", "Costs are manageable.")]
        path = tmp_project.save_session(r, qa)
        content = Path(path).read_text()
        assert "What about costs?" in content
        assert "Costs are manageable." in content

    def test_empty_qa_pairs(self, tmp_project):
        tmp_project.load()
        path = tmp_project.save_session(self._make_result(), [])
        # Should not raise and file should exist
        assert Path(path).exists()


class TestUpdateBrief:
    def _make_result(self):
        r = MagicMock()
        r.problem = "Build a B2B SaaS?"
        r.synthesis = "Strong market fit, high execution risk."
        r.recommendations = ["Start with 3 design partners", "Avoid consumer"]
        return r

    def test_calls_client_chat(self, tmp_project):
        tmp_project.load()
        client = MagicMock()
        client.chat.return_value = "## Stage\nUpdated\n"
        tmp_project.update_brief(client, self._make_result(), [])
        assert client.chat.called

    def test_writes_new_brief_to_disk(self, tmp_project):
        tmp_project.load()
        client = MagicMock()
        client.chat.return_value = "## Stage\nPost-brief-update\n"
        tmp_project.update_brief(client, self._make_result(), [])
        content = tmp_project.brief_path.read_text()
        assert "Post-brief-update" in content

    def test_returns_new_brief_text(self, tmp_project):
        tmp_project.load()
        client = MagicMock()
        client.chat.return_value = "## Stage\nReturned\n"
        result = tmp_project.update_brief(client, self._make_result(), [])
        assert "Returned" in result

    def test_passes_current_brief_to_llm(self, tmp_project):
        tmp_project.load()
        client = MagicMock()
        client.chat.return_value = "## Stage\nOK\n"
        tmp_project.update_brief(client, self._make_result(), [])
        _, user_prompt = client.chat.call_args[0]
        assert "Current brief" in user_prompt

    def test_includes_qa_in_prompt(self, tmp_project):
        tmp_project.load()
        client = MagicMock()
        client.chat.return_value = "## Stage\nOK\n"
        qa = [("What about pricing?", "Usage-based is best.")]
        tmp_project.update_brief(client, self._make_result(), qa)
        _, user_prompt = client.chat.call_args[0]
        assert "What about pricing?" in user_prompt
