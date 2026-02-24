import os
import tempfile

import pytest
from unittest.mock import MagicMock, patch

from src.llm.prompts import ALL_AGENT_NAMES
from src.main import main


class TestListAgents:
    def test_list_agents_prints_names(self, capsys):
        with patch("sys.argv", ["prog", "--list-agents"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        output = capsys.readouterr().out
        for name in ALL_AGENT_NAMES:
            assert name in output

    def test_list_agents_sorted(self, capsys):
        with patch("sys.argv", ["prog", "--list-agents"]):
            with pytest.raises(SystemExit):
                main()

        lines = capsys.readouterr().out.strip().splitlines()
        assert lines == sorted(lines)


class TestMainEntrypoint:
    def test_no_problem_interactive_empty_exits(self, capsys):
        with patch("sys.argv", ["prog"]):
            with patch("builtins.input", return_value=""):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

        assert "No problem provided" in capsys.readouterr().out

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_basic_run(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem"]):
            main()

        mock_mediator_cls.return_value.analyze.assert_called_once_with("test problem")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_output_flag_calls_export(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result
        mock_export.return_value = "output/test/2026-01-01T00-00-00"

        with patch("sys.argv", ["prog", "test", "--output"]):
            main()

        mock_export.assert_called_once_with(mock_result, "default")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_report_flag(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--report", "--output"]):
            main()

        mock_export.assert_called_once_with(mock_result, "detailed")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_customer_report_flag(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--customer-report", "--output"]):
            main()

        mock_export.assert_called_once_with(mock_result, "customer")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_exit(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", return_value="exit"):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_empty(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", return_value=""):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_eof(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", side_effect=EOFError):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_calls_followup(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator = mock_mediator_cls.return_value
        mock_mediator.analyze.return_value = mock_result
        mock_mediator.followup.return_value = "Follow-up answer"

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", side_effect=["What about costs?", "exit"]):
                main()

        mock_mediator.followup.assert_called_once_with(mock_result, "What about costs?")



class TestAutoSelectFlag:
    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_auto_select_on_by_default(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["auto_select"] is True

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_no_auto_select_disables_it(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--no-auto-select"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["auto_select"] is False


class TestUserContext:
    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_context_flag_passed_to_mediator(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--context", "Bootstrapped SaaS, 2 founders"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["user_context"] == "Bootstrapped SaaS, 2 founders"

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_no_context_passes_none(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["user_context"] is None

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_context_file_loaded(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("VC-backed, Series A, $2M ARR")
            tmp_path = f.name
        try:
            with patch("sys.argv", ["prog", "test", "--context-file", tmp_path]):
                main()
            _, kwargs = mock_mediator_cls.call_args
            assert kwargs["user_context"] == "VC-backed, Series A, $2M ARR"
        finally:
            os.unlink(tmp_path)

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_context_flag_takes_priority_over_file(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("From file")
            tmp_path = f.name
        try:
            with patch("sys.argv", ["prog", "test", "--context", "From flag", "--context-file", tmp_path]):
                main()
            _, kwargs = mock_mediator_cls.call_args
            assert kwargs["user_context"] == "From flag"
        finally:
            os.unlink(tmp_path)


class TestProjectFlag:
    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_project_flag_loads_brief_into_user_context(self, mock_client_cls, mock_mediator_cls, mock_export, tmp_path):
        """--project causes brief to be prepended to user_context passed to Mediator."""
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        project_dir = str(tmp_path / "proj")
        with patch("sys.argv", ["prog", "test problem", "--project", project_dir]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["user_context"] is not None
        assert "Project brief" in kwargs["user_context"]

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_project_flag_merges_with_context(self, mock_client_cls, mock_mediator_cls, mock_export, tmp_path):
        """--project brief is prepended when --context is also given."""
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        project_dir = str(tmp_path / "proj")
        with patch("sys.argv", [
            "prog", "test", "--project", project_dir, "--context", "Bootstrapped"
        ]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        ctx = kwargs["user_context"]
        assert "Project brief" in ctx
        assert "Bootstrapped" in ctx

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_with_project_writes_session_file(
        self, mock_client_cls, mock_mediator_cls, mock_export, tmp_path
    ):
        """Interactive mode + --project writes a session file on exit."""
        mock_result = MagicMock()
        mock_result.agent_outputs = []
        mock_result.problem = "Test"
        mock_result.synthesis = "OK"
        mock_result.recommendations = []
        mock_mediator = mock_mediator_cls.return_value
        mock_mediator.analyze.return_value = mock_result
        mock_mediator.followup.return_value = "Some answer"

        # Mock client.chat for update_brief
        mock_client = mock_client_cls.return_value
        mock_client.chat.return_value = "## Stage\nUpdated\n"

        project_dir = str(tmp_path / "proj")
        with patch("sys.argv", [
            "prog", "test problem", "--project", project_dir, "--interactive"
        ]):
            with patch("builtins.input", side_effect=["What about costs?", "exit"]):
                main()

        sessions_dir = tmp_path / "proj" / "sessions"
        session_files = list(sessions_dir.glob("*.md"))
        assert len(session_files) == 1
        content = session_files[0].read_text()
        assert "What about costs?" in content


class TestListAgentsExpanded:
    def test_list_agents_shows_all_12(self, capsys):
        with patch("sys.argv", ["prog", "--list-agents"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        output = capsys.readouterr().out
        for name in ALL_AGENT_NAMES:
            assert name in output

    def test_list_agents_no_markers(self, capsys):
        with patch("sys.argv", ["prog", "--list-agents"]):
            with pytest.raises(SystemExit):
                main()

        output = capsys.readouterr().out
        assert "(default)" not in output
        assert "(pool)" not in output
