import argparse

import pytest
from unittest.mock import MagicMock, patch

from src.llm.prompts import ALL_MODULE_NAMES
from src.main import main, parse_weight, DEFAULT_MODULE_NAMES, VALID_MODULE_NAMES


class TestParseWeight:
    def test_valid_weight(self):
        assert parse_weight("legal=2") == ("legal", 2.0)

    def test_valid_weight_float(self):
        assert parse_weight("cost=1.5") == ("cost", 1.5)

    def test_valid_weight_zero(self):
        assert parse_weight("tech=0") == ("tech", 0.0)

    def test_missing_equals(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid weight format"):
            parse_weight("legal")

    def test_unknown_module(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Unknown module"):
            parse_weight("unknown=2")

    def test_non_numeric_weight(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid weight value"):
            parse_weight("legal=abc")

    def test_negative_weight(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must be non-negative"):
            parse_weight("legal=-1")


class TestListModules:
    def test_list_modules_prints_names(self, capsys):
        with patch("sys.argv", ["prog", "--list-modules"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        output = capsys.readouterr().out
        for name in sorted(VALID_MODULE_NAMES):
            assert name in output

    def test_list_modules_sorted(self, capsys):
        with patch("sys.argv", ["prog", "--list-modules"]):
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
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem"]):
            main()

        mock_mediator_cls.return_value.analyze.assert_called_once_with("test problem")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_weight_passed_to_mediator(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--weight", "legal=2", "--weight", "cost=0"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["weights"] == {"legal": 2.0, "cost": 0.0}

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_output_flag_calls_export(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
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
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--report", "--output"]):
            main()

        mock_export.assert_called_once_with(mock_result, "detailed")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_customer_report_flag(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--customer-report", "--output"]):
            main()

        mock_export.assert_called_once_with(mock_result, "customer")

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_exit(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", return_value="exit"):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_empty(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", return_value=""):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_flag_exits_on_eof(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test problem", "--interactive"]):
            with patch("builtins.input", side_effect=EOFError):
                main()

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_interactive_calls_followup(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
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
    def test_auto_select_passed_to_mediator(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--auto-select"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["auto_select"] is True

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_no_auto_select_by_default(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["auto_select"] is False

    @patch("src.main.export_all")
    @patch("src.main.Mediator")
    @patch("src.main.ClaudeClient")
    def test_auto_select_with_weights(self, mock_client_cls, mock_mediator_cls, mock_export):
        mock_result = MagicMock()
        mock_result.module_outputs = []
        mock_mediator_cls.return_value.analyze.return_value = mock_result

        with patch("sys.argv", ["prog", "test", "--auto-select", "--weight", "legal=2"]):
            main()

        _, kwargs = mock_mediator_cls.call_args
        assert kwargs["auto_select"] is True
        assert kwargs["weights"] == {"legal": 2.0}


class TestListModulesExpanded:
    def test_list_modules_shows_all_12(self, capsys):
        with patch("sys.argv", ["prog", "--list-modules"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

        output = capsys.readouterr().out
        for name in ALL_MODULE_NAMES:
            assert name in output

    def test_list_modules_shows_markers(self, capsys):
        with patch("sys.argv", ["prog", "--list-modules"]):
            with pytest.raises(SystemExit):
                main()

        output = capsys.readouterr().out
        assert "(default)" in output
        assert "(auto-select pool)" in output


class TestValidModuleNamesExpanded:
    def test_valid_module_names_includes_all_12(self):
        assert len(VALID_MODULE_NAMES) == 12
        for name in ALL_MODULE_NAMES:
            assert name in VALID_MODULE_NAMES

    def test_pool_modules_accepted_in_weight(self):
        # e.g. --weight political=2 should be valid
        name, weight = parse_weight("political=2")
        assert name == "political"
        assert weight == 2.0
