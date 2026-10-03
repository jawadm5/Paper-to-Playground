"""Credential lookup regression checks without real keys or network requests."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from playground_v2.cli import _load_api_key, main


ROOT = Path(__file__).resolve().parent.parent
TEST_KEY = "synthetic-saved-user-key"


class V2CliTests(unittest.TestCase):
    def setUp(self):
        self.registry = MagicMock()
        self.registry.QueryValueEx.return_value = (f"  {TEST_KEY}  ", 1)
        self.platform = patch("playground_v2.cli.sys.platform", "win32")
        self.modules = patch.dict("sys.modules", {"winreg": self.registry})
        self.environment = patch.dict(os.environ, {"OPENROUTER_API_KEY": ""})
        for context in (self.platform, self.modules, self.environment):
            context.start()
            self.addCleanup(context.stop)

    def test_current_terminal_key_takes_precedence(self):
        os.environ["OPENROUTER_API_KEY"] = "  synthetic-process-key  "
        self.assertEqual(_load_api_key(), "synthetic-process-key")
        self.registry.OpenKey.assert_not_called()

    def test_windows_saved_user_key_is_loaded_without_mutating_environment(self):
        self.assertEqual(_load_api_key(), TEST_KEY)
        self.registry.OpenKey.assert_called_once_with(self.registry.HKEY_CURRENT_USER, "Environment")
        handle = self.registry.OpenKey.return_value.__enter__.return_value
        self.registry.QueryValueEx.assert_called_once_with(handle, "OPENROUTER_API_KEY")
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], "")

    def test_non_windows_does_not_query_registry(self):
        with patch("playground_v2.cli.sys.platform", "linux"):
            self.assertEqual(_load_api_key(), "")
        self.registry.OpenKey.assert_not_called()

    def test_missing_or_unreadable_user_environment_is_handled(self):
        for error in (FileNotFoundError(), PermissionError()):
            with self.subTest(error=type(error).__name__):
                self.registry.OpenKey.side_effect = error
                self.assertEqual(_load_api_key(), "")

    def test_missing_or_non_text_key_is_handled(self):
        self.registry.QueryValueEx.side_effect = FileNotFoundError()
        self.assertEqual(_load_api_key(), "")
        self.registry.QueryValueEx.side_effect = None
        for value in (None, 1, b"not-text", "   "):
            with self.subTest(value=value):
                self.registry.QueryValueEx.return_value = (value, 1)
                self.assertEqual(_load_api_key(), "")

    def test_cli_passes_saved_key_and_redacts_errors(self):
        captured = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            args = ["--input", str(ROOT / "examples/v2-attention.json"),
                    "--output", str(Path(directory) / "out"), "--model", "test/model"]
            with patch("playground_v2.cli.run", return_value=0) as runner, \
                    redirect_stdout(captured), redirect_stderr(captured):
                self.assertEqual(main(args), 0)
            self.assertEqual(runner.call_args.kwargs["key"], TEST_KEY)
            with patch("playground_v2.cli.run", side_effect=ValueError(f"Failed for {TEST_KEY}")), \
                    redirect_stdout(captured), redirect_stderr(captured):
                self.assertEqual(main(args), 2)
        self.assertNotIn(TEST_KEY, captured.getvalue())
        self.assertIn("[REDACTED]", captured.getvalue())

    def test_prepare_only_does_not_load_a_key(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("playground_v2.cli.run", return_value=0) as runner, \
                patch("playground_v2.cli._load_api_key") as loader, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--input", str(ROOT / "examples/v2-attention.json"),
                                   "--output", str(Path(directory) / "out"), "--prepare-only"]), 0)
        loader.assert_not_called()
        self.assertEqual(runner.call_args.kwargs["key"], "")
