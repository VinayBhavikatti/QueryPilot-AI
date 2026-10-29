import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.llm import generate_sql, summarize


class LlmResponseTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(_env_file=None, _env_prefix="__TEST__")
        self.client = Mock()
        self.completions = self.client.chat.completions
        self.settings_patch = patch("app.llm.get_settings", return_value=self.settings)
        self.client_patch = patch("app.llm._client", return_value=self.client)
        self.settings_patch.start()
        self.client_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(self.client_patch.stop)

    def set_response(self, content):
        self.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    def test_sql_generation_disables_thinking_and_returns_content(self):
        self.set_response("SELECT 1")

        result = generate_sql("count rows", "items(id)", [])

        self.assertEqual(result, "SELECT 1")
        self.assertEqual(self.completions.create.call_args.kwargs["max_tokens"], 700)
        self.assertEqual(
            self.completions.create.call_args.kwargs["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )

    def test_summary_disables_thinking_and_returns_content(self):
        self.set_response("There is one row.")

        result = summarize("count rows", "SELECT 1", ["count"], [{"count": 1}])

        self.assertEqual(result, "There is one row.")
        self.assertEqual(self.completions.create.call_args.kwargs["max_tokens"], 250)
        self.assertEqual(
            self.completions.create.call_args.kwargs["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )

    def test_empty_sql_content_fails_closed(self):
        for content in (None, "", "   "):
            with self.subTest(content=content):
                self.set_response(content)
                with self.assertRaisesRegex(RuntimeError, "empty content for SQL generation"):
                    generate_sql("count rows", "items(id)", [])

    def test_empty_summary_content_fails_closed(self):
        for content in (None, "", "   "):
            with self.subTest(content=content):
                self.set_response(content)
                with self.assertRaisesRegex(RuntimeError, "empty content for result summarization"):
                    summarize("count rows", "SELECT 1", ["count"], [{"count": 1}])

    def test_missing_choices_fail_closed(self):
        self.completions.create.return_value = SimpleNamespace(choices=[])

        with self.assertRaisesRegex(RuntimeError, "no completion choices for SQL generation"):
            generate_sql("count rows", "items(id)", [])

        with self.assertRaisesRegex(RuntimeError, "no completion choices for result summarization"):
            summarize("count rows", "SELECT 1", ["count"], [{"count": 1}])


if __name__ == "__main__":
    unittest.main()
